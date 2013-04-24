# pyclewn-nodedbg

pyclewn-nodedbg は、Vim 上で Node.js スクリプトのデバッグを行うための、
Pyclewn 用の追加クラスです.

## Requirements

* [Pyclewn](http://pyclewn.sourceforge.net)
* [Vim](http://www.vim.org)
* [Node.js](http://nodejs.org)

Vim と Node.js は古いバージョンでなければ対応できてるとは思いますが、
Pyclewn は **Python3 用** が必要ですので注意してください.

## Installation

`clewn/*` を Pyclewn の python ディレクトリ(`$HOME/lib/python/clewn` 等) へコピーし、
`patch/*` をそれぞれのファイルへ適用します
(`$HOME/lib/python/clewn/vim.py` `$HOME/.vim/autostart/pyclewn.vim` 等).

## Quick Start

`foo.js` スクリプトのデバッグ.

    $ node --debug-brk foo.js
    $ pyclewn --nodedbg -e gvim
    または
    $ node --debug-brk foo.js
    :Pyclewn nodedbg

`foo.js` の 5 行目に breakpoint をセットし、continue する.

    :Cbreak foo.js:5
    :Ccontinue

変数 `bar` の表示と変更.

    :Cprint bar
    :Cprint bar=10

`<C-B>` による breakpoint セットや `<S-C>` による continue 等のキーマップ有効化.

    :Cmapkeys

その他の有効なコマンドの表示.

    :Chelp

## Known Issues

現状では、
nodedbg からNode.jsのスクリプトを直接起動することには対応してません.
また、Node.js の debugger へ接続するときは、`localhost:5858` 固定です.

`Cbreak foo.js:10` のような breakpoint 追加コマンドの実行時に、
対象のスクリプトファイル (`foo.js`) が Node.js 側で読み込まれていない場合、
breakpoint の追加は失敗します.

設定された breakpoint は (ターゲットが終了するなどで)、
Node.js との接続が切れるとすべて clear されます.
接続が回復しても、現状では再設定されません.

キーボードから `<C-S>` (`Cstep` コマンド)を連続して実行したりすると、
以下のようなエラーとなるかもしれません.

    "deque index out of range"
    source line: "del self.producer_fifo[0]"
    at /usr/lib/python3.3/asynchat.py:254

Node.js の debugger へ接続できないときに、
適切なエラーメッセージが表示されません.
(`Node.js debugger connection closed.` とは表示されます).

まだそれほど(というか殆ど)使い込んでないので、
他にもいろいろあるんじゃないかと思います.


## Thanks

Node.js の `--debug` オプションや、v8 debugger protocolの扱いについて、
[Node Inspector](http://github.com/dannycoates/node-inspector) と
[DebuggerProtocol](https://code.google.com/p/v8/wiki/DebuggerProtocol)
を参考にさせていただきました.

[Pyclewn](http://pyclewn.sourceforge.net) のクラス拡張が利用できたため、
わりとお手軽に、Vim 上での Node.js 用 Debugger UI が作成できました.

ありがとうございました.

## License

Copyright (c) 2013 hankei6km (MIT License)

* `clewn/nodedbg.py` は Pyclewn の simple.py を元に作成しました.

* `clewn/nodeclient.py` の一部のメソッドは、
Node-Inspector の lib/client.js と lib/protocol.js 内のコードを元に作成しました.

