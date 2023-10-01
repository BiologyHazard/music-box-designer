# MusicBoxDesigner
[![License](https://img.shields.io/github/license/BiologyHazard/MusicBoxDesigner?style=flat-square)](https://github.com/BiologyHazard/MusicBoxDesigner/blob/main/LICENSE)
[![Release](https://img.shields.io/github/release/BiologyHazard/MusicBoxDesigner?style=flat-square)](https://github.com/Mrs4s/go-cqhttp/releases)


主要功能

- .mid, .emid, .fmp 文件之间互相转换
- 生成纸带设计稿图片

作者：[bilibili@Bio-Hazard](https://space.bilibili.com/37179776)
- QQ [3482991796](https://wpa.qq.com/msgrd?&uin=3482991796)
- QQ群 [586134350](https://qm.qq.com/cgi-bin/qm/qr?k=aM1lRdY9HvrQW3huC81hRmCQaE7CkyXh)

FairyMusicBox 系列软件作者：[bilibili@调皮的码农](https://space.bilibili.com/40962795)

FairyMusicBox 官网：http://www.fairymusicbox.com/


# 提示

FairyMusicBox 3.0.0 实现了本程序的几乎全部功能。如果您只是想进行一些基本的操作（生成纸带设计稿等），建议使用 FairyMusicBox。


# 安装

1. 安装 Python（3.9及以上）

    - Windows 系统

        按快捷键 Win + R 输入 cmd 回车，在弹出的窗口中输入
        ```
        python --version
        ```
        检查 Python 版本是否大于等于 3.9。如果报错或者版本过低，您需要按照下面的方法安装 Python。

        > 请自行前往 https://www.python.org/ 下载 Python（3.9及以上）并将 Python 添加到环境变量（在安装过程中勾选 "Add Python to system PATH"）。

        > 对大多数用户来说，您应该下载 Windows installer (64-bit)。

    - macOS 系统 以及 Linux 系统

        相信您有能力自己搞定！

1. pip 安装依赖

    运行命令
    ```
    pip install -r requirements.txt
    ```

# 代码示例

- 把 examples/example.emid 转换成 midi 格式并保存到 examples/example.mid

    ```python
    from mido import MidiFile
    from musicboxdesigner.emid import EmidFile

    emid_file = EmidFile.load_from_file('examples/example.emid')
    midi_file = emid_file.export_midi()
    midi_file.save('examples/example.mid')

    # or in a single line:
    EmidFile.load_from_file('examples/example.emid').export_midi().save('examples/example.mid')
    ```

- 把 examples/example.midi 转换成 emid 格式并保存到 examples/example.emid

    ```python
    from mido import MidiFile
    from musicboxdesigner.emid import EmidFile

    midi_file = MidiFile('examples/example.mid')
    emid_file = EmidFile.from_midi(midi_file)
    emid_file.save_to_file('examples/example.emid')

    # or in a single line:
    EmidFile.from_midi(MidiFile('examples/example.mid')).save_to_file('examples/example.emid')
    ```

- 对 fmp 的支持是类似的

    ```python
    from mido import MidiFile
    from musicboxdesigner.fmp import FmpFile

    FmpFile.load_from_file('examples/example.fmp').export_midi().save('examples/example.mid')
    # and
    FmpFile.from_midi(MidiFile('examples/example.mid')).save_to_file('examples/example.fmp')
    ```

- 从 examples/example.mid 生成纸带设计稿

    ```python
    from musicboxdesigner.draft import Draft, DraftSettings

    # load settings from draft_settings.json
    with open('draft_settings.json', 'r', encoding='utf-8') as fp:
        settings: DraftSettings = DraftSettings.model_validate_json(fp.read())

    # or just create a DraftSettings instance with default or custom values
    settings = DraftSettings(show_subtitle=False, show_bar_count=False)

    Draft.load_from_file('examples/example.mid').export_pics(
        settings=settings,
        title='Your title',
        subtitle='''Your subtitle''',
    ).save()
    ```


# Issue

如果在使用过程中遇到了问题，请点击页面顶部的 Issue -> New Issue，并详细描述您的问题。


# TODO

- 自定义水印
- 显示小节号
- 更多的快捷方法以及批处理方法
- 用户友好的README
- 自动打包

祝使用愉快！
