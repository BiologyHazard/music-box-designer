"""
Recognize music box paper strip from image or pdf file.
"""

from collections.abc import Generator, Iterable
from pathlib import Path
from typing import Any, NamedTuple

import cv2
import fitz
import mido
import numpy as np
from cv2.typing import MatLike
from mido import Message, MetaMessage, MidiFile, MidiTrack
from numpy.typing import NDArray

from .consts import DEFAULT_DURATION, MIDI_DEFAULT_TICKS_PER_BEAT
from .log import logger
from .presets import music_box_30_notes

type Pos_T = tuple[float, float]


class Note(NamedTuple):
    index: int
    row: float


images_path = Path("images")


def _load_image(image: str | Path | bytes | MatLike) -> MatLike:
    if isinstance(image, str):
        return cv2.imdecode(np.fromfile(image, dtype=np.uint8), cv2.IMREAD_COLOR)
    elif isinstance(image, Path):
        return cv2.imdecode(np.fromfile(image, dtype=np.uint8), cv2.IMREAD_COLOR)
    elif isinstance(image, (bytes, bytearray, memoryview)):
        return cv2.imdecode(np.frombuffer(image, dtype=np.uint8), cv2.IMREAD_COLOR)
    else:
        return image


def _save_image(image: MatLike, filename: str) -> None:
    file_path: Path = images_path / filename
    file_path.parent.mkdir(parents=True, exist_ok=True)
    success, buffer = cv2.imencode(".png", image)
    file_path.write_bytes(buffer)
    # if cv2.imwrite(file_path.as_posix(), image):
    #     logger.debug(f'Saved image to {file_path.as_posix()}')
    # else:
    #     logger.error(f'Failed to save image to {file_path.as_posix()}')


def pdf_to_images(pdf_path: str | Path, dpi=300) -> Generator[bytes, Any, None]:
    pdf_document: fitz.Document = fitz.open(pdf_path)  # type: ignore
    for page in pdf_document:
        pixmap: fitz.Pixmap = page.get_pixmap(dpi=dpi, alpha=False)  # type: ignore
        yield pixmap.tobytes()


def remove_near_lines(lines: NDArray) -> NDArray:
    median: float = float(np.median(np.diff(lines)))
    min_distance: float = median * 2 / 3
    result: list[float] = []
    for line in lines:
        if not result:
            result.append(line)
            continue
        if min_distance <= line - result[-1]:
            result.append(line)
        else:
            result[-1] = (result[-1] + line) / 2
    return np.array(result)


def remove_far_lines(lines: NDArray) -> NDArray:
    median: float = float(np.median(np.diff(lines)))
    max_distance: float = median * 4 / 3
    result: list[float] = []
    for i, x in enumerate(lines):
        left = lines[i] - lines[i - 1] if i > 0 else np.inf
        right = lines[i + 1] - lines[i] if i < len(lines) - 1 else np.inf
        if left <= max_distance or right <= max_distance:
            result.append(x)
    return np.array(result)


def detect_vertical_lines(image: MatLike, page: int) -> NDArray[np.float32]:
    gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    kernel = np.ones((41, 1), np.uint8)
    morph_close_image = cv2.morphologyEx(
        gray_image, cv2.MORPH_CLOSE, kernel, iterations=1
    )
    threshold, binary_image = cv2.threshold(
        morph_close_image, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU
    )
    height, width = binary_image.shape
    hough_lines_result = cv2.HoughLines(binary_image, 1, np.pi, height // 8)
    lines_x = np.around(hough_lines_result[:, 0, 0])
    lines_x.sort()
    valid_lines_x = remove_near_lines(lines_x)
    valid_lines_x = remove_far_lines(valid_lines_x)

    logger.debug(f"Vertical lines: {len(valid_lines_x)}")
    if len(valid_lines_x) % 30 != 0:
        logger.warning(
            f"Vertical lines not divisible by 30, check vertical_lines.png for details"
        )

    output_image = image.copy()
    for x in np.around(lines_x).astype(int):
        cv2.line(output_image, (x, 0), (x, height), (255, 0, 0), 2)
    for x in np.around(valid_lines_x).astype(int):
        cv2.line(output_image, (x, 0), (x, height), (0, 0, 255), 2)
    _save_image(output_image, "vertical_lines.png")

    return valid_lines_x


def divide_columns(image: MatLike, page: int) -> list[tuple[float, float]]:
    vertical_lines = detect_vertical_lines(image, page)
    median: float = float(np.median(np.diff(vertical_lines)))
    max_distance: float = median * 4 / 3
    dividers: list[float] = []
    for i, x in enumerate(vertical_lines):
        left = vertical_lines[i] - vertical_lines[i - 1] if i > 0 else np.inf
        right = (
            vertical_lines[i + 1] - vertical_lines[i]
            if i < len(vertical_lines) - 1
            else np.inf
        )
        if left > max_distance or right > max_distance:
            dividers.append(x)
    if len(dividers) % 2 != 0:
        raise Exception(
            "Failed to divide columns, check vertical_lines.png for details"
        )

    result: list[tuple[float, float]] = [
        (dividers[i], dividers[i + 1]) for i in range(0, len(dividers), 2)
    ]
    result_array = np.array(result)
    column_widths = result_array[:, 1] - result_array[:, 0]
    if column_widths.std() > column_widths.mean() / 10:
        raise Exception(
            "Failed to divide columns, check vertical_lines.png for details"
        )

    logger.debug(f"Columns: {result}")
    output_image = image.copy()
    for x in np.around(dividers).astype(int):
        cv2.line(output_image, (x, 0), (x, image.shape[0]), (0, 255, 0), 2)
    _save_image(output_image, "divide_columns.png")

    return result


def detect_horizontal_lines(
    image: MatLike, page: int, column_no: int
) -> NDArray[np.float32]:
    transposed_image = image.transpose(1, 0, 2)
    gray_image = cv2.cvtColor(transposed_image, cv2.COLOR_BGR2GRAY)
    kernel = np.ones((21, 1), np.uint8)
    morph_close_image = cv2.morphologyEx(
        gray_image, cv2.MORPH_CLOSE, kernel, iterations=1
    )
    _, binary_image = cv2.threshold(
        morph_close_image, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU
    )
    height, width = binary_image.shape
    hough_lines_result = cv2.HoughLines(binary_image, 1, np.pi, height // 2)
    lines_y = np.around(hough_lines_result[:, 0, 0])
    lines_y.sort()
    valid_lines_y = remove_near_lines(lines_y)
    valid_lines_y = remove_far_lines(valid_lines_y)

    logger.debug(f"Horizontal lines: {len(valid_lines_y)}")
    output_image = transposed_image.copy()
    for x in np.around(lines_y).astype(int):
        cv2.line(output_image, (x, 0), (x, height), (255, 0, 0), 2)
    for x in np.around(valid_lines_y).astype(int):
        cv2.line(output_image, (x, 0), (x, height), (0, 0, 255), 2)
    _save_image(output_image.transpose(1, 0, 2), f"horizontal_lines_{column_no}.png")

    return valid_lines_y


def detect_columns(image: MatLike, page: int) -> list[tuple[Pos_T, Pos_T]]:
    columns: list[tuple[float, float]] = divide_columns(image, page)
    output_image = image.copy()
    result: list[tuple[Pos_T, Pos_T]] = []
    for i, (x1, x2) in enumerate(columns):
        horizontal_lines = detect_horizontal_lines(
            image[:, round(x1) : round(x2)], page, i
        )
        y1, y2 = horizontal_lines[0], horizontal_lines[-1]
        result.append(((x1, y1), (x2, y2)))
        cv2.rectangle(
            output_image, (round(x1), round(y1)), (round(x2), round(y2)), (0, 255, 0), 2
        )

    logger.debug(f"Columns: {result}")
    _save_image(output_image, f"columns_{page}.png")

    return result


def detect_circles(image: MatLike, page: int) -> list[tuple[float, float, float]]:
    gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    kernel = np.ones((7, 7), np.uint8)
    morph_close_image = cv2.morphologyEx(
        gray_image, cv2.MORPH_CLOSE, kernel, iterations=1
    )
    # save_image(morph_close_image, 'morph_close.png')
    # morph_close_image = cv2.threshold(morph_close_image, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
    circles = cv2.HoughCircles(
        morph_close_image,
        cv2.HOUGH_GRADIENT,
        dp=1.1,
        minDist=15,
        param1=100,
        param2=20,
        minRadius=5,
        maxRadius=20,
    )[0]
    valid_circles = []
    for x, y, r in circles:
        x1 = round(x - r * np.sqrt(2) / 2)
        x2 = round(x + r * np.sqrt(2) / 2)
        y1 = round(y - r * np.sqrt(2) / 2)
        y2 = round(y + r * np.sqrt(2) / 2)
        if morph_close_image[y1:y2, x1:x2].mean() < 128:
            valid_circles.append((x, y, r))

    logger.debug(f"Circles: {len(valid_circles)}")
    output_image = cv2.cvtColor(morph_close_image.copy(), cv2.COLOR_GRAY2BGR)
    for x, y, r in np.around(valid_circles).astype(int):
        cv2.circle(output_image, (x, y), r, (0, 255, 0), 2)
        cv2.circle(output_image, (x, y), 2, (0, 0, 255), 3)
    _save_image(output_image, f"circles_{page}.png")

    return valid_circles


def get_notes(
    circles: list[tuple[float, float, float]],
    columns_start_end: list[tuple[Pos_T, Pos_T]],
    row_passed: float = 0,
) -> tuple[list[Note], float]:
    columns_start_end_array = np.array(columns_start_end)
    column_widths = columns_start_end_array[:, 1, 0] - columns_start_end_array[:, 0, 0]
    column_heights = columns_start_end_array[:, 1, 1] - columns_start_end_array[:, 0, 1]
    grid_widths = column_widths / 29
    half_rows = np.around(column_heights / grid_widths * 2 / 4).astype(int)
    accumulate_half_rows = np.insert(np.cumsum(half_rows), 0, 0)
    row_heights = column_heights / half_rows * 2

    logger.debug(f"Grid widths: {grid_widths}")
    logger.debug(f"Half rows: {half_rows}")
    logger.debug(f"Row heights: {row_heights}")

    result: list[Note] = []
    for x, y, r in sorted(circles, key=lambda circle: circle[0]):
        for col, ((x1, y1), (x2, y2)) in enumerate(columns_start_end):
            if (
                x1 - grid_widths[col] / 2 <= x <= x2 + grid_widths[col] / 2
                and y1 - grid_widths[col] / 2 <= y <= y2 + grid_widths[col] / 2
            ):
                break
        else:
            logger.warning(f"Circle at ({x}, {y}) not in any column")
            continue

        index: int = round((x - columns_start_end[col][0][0]) / grid_widths[col])
        row: float = (y - columns_start_end[col][0][1]) / row_heights[col]
        result.append(Note(index, row_passed + accumulate_half_rows[col] / 2 + row))

    return result, row_passed + accumulate_half_rows.item(-1) / 2


def quantize_notes(
    notes: Iterable[Note], quantization: float | None = 1 / 4
) -> Iterable[Note]:
    if quantization is None or quantization == 0:
        return notes
    return (
        Note(note.index, round(note.row / quantization) * quantization)
        for note in notes
    )


def export_midi(
    notes: list[Note],
    quantization: float | None = 1 / 4,
    ticks_per_beat: int = MIDI_DEFAULT_TICKS_PER_BEAT,
) -> MidiFile:
    midi_file = MidiFile(charset="gbk")
    midi_file.ticks_per_beat = ticks_per_beat

    midi_track = MidiTrack()
    midi_track.name = f"Track 0"
    midi_track.append(Message(type="program_change", program=10, time=0))
    for note in sorted(quantize_notes(notes, quantization), key=lambda note: note.row):
        midi_track.append(
            Message(
                type="note_on",
                note=music_box_30_notes.range[note.index],
                time=round(note.row * ticks_per_beat),
            )
        )
        midi_track.append(
            Message(
                type="note_off",
                note=music_box_30_notes.range[note.index],
                time=round((note.row + DEFAULT_DURATION) * ticks_per_beat),
            )
        )
    midi_track.sort(key=lambda message: message.time)
    midi_track = MidiTrack(mido.midifiles.tracks._to_reltime(midi_track))
    midi_track.append(MetaMessage(type="end_of_track", time=0))
    midi_file.tracks.append(midi_track)
    return midi_file


def recognize_image(image: MatLike) -> list[Note]:
    return get_notes(detect_circles(image, 0), detect_columns(image, 0))[0]


def recognize_multi_image(images: Iterable[str | Path | bytes | MatLike]) -> list[Note]:
    all_notes = []
    row_passed = 0
    for i, image in enumerate(images):
        image = _load_image(image)
        logger.info(f"Processing page {i + 1}...")
        notes, row_passed = get_notes(
            detect_circles(image, i), detect_columns(image, i), row_passed
        )
        all_notes.extend(notes)
    return all_notes


def recognize_pdf(pdf_path: str | Path) -> list[Note]:
    return recognize_multi_image(pdf_to_images(pdf_path))
