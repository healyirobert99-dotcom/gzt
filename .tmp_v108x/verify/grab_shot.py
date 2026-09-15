# -*- coding: utf-8 -*-
"""把 agent-browser 最新一张截图复制到指定位置。

`screenshot` 的单参数会被当成 selector，所以图实际落在
`~/.agent-browser/tmp/screenshots/`；这里按 mtime 取最新一张拷走。
用法：python grab_shot.py <目标路径>
"""
import os
import shutil
import sys

SRC = os.path.join(os.path.expanduser('~'), '.agent-browser', 'tmp',
                   'screenshots')


def main():
    dst = sys.argv[1]
    files = [os.path.join(SRC, f) for f in os.listdir(SRC)
             if f.lower().endswith('.png')]
    if not files:
        print('no screenshot found in %s' % SRC)
        return 1
    newest = max(files, key=os.path.getmtime)
    d = os.path.dirname(os.path.abspath(dst))
    if not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)
    shutil.copyfile(newest, dst)
    print('copied %s -> %s (%d bytes)'
          % (os.path.basename(newest), dst, os.path.getsize(dst)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
