# vi:set ts=8 sts=4 sw=4 et tw=80:
#
# @author hankei6km
# @copyright (c) 2013 hankei6km
# @license MIT License (http://opensource.org/licenses/mit-license.php)
#
# NodeClient.send_req および NodeClient.dbg_* メソッドは、
# Node Inspector (http://github.com/dannycoates/node-inspector) に含まれる
# lib/client.js と lib/protocol.js 内からコードをコピーし
# Pythonへの変換とNodeClientクラス用に変更したものです.
# Node Inspector のライセンスについては、同梱の LICENSE.node-inspector を参照.


import asyncore
import asynchat
import socket
import json

import time

from .nodeutils import parse_headers 

DEBUG_HOST = 'localhost'
DEBUG_PORT = 5858

class NodeClient(asynchat.async_chat):
    """Node.js の debugger を非同期に制御するクラス."""
    def __init__(self, handle_resp):
        asynchat.async_chat.__init__(self)
        self.ibuffer = []

        self._handle_resp = handle_resp
        return
    
    def connect_start(self):
        """ debugger と接続する."""
        self.set_terminator(b'\r\n\r\n')
        self.reading_headers = True
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connect((DEBUG_HOST, DEBUG_PORT))
        return

    def handle_error(self):
        # TODO: 主に `[Errno 111] Connection refused` だが、
        # 状況にあわせたメッセージの表示等を追加.
        self.close()
        return

    def handle_connect(self):
        # TODO: setexceptionbreak をコマンドにする.
        # all のみで uncaught が効かないようなので、現状ではなにもしない.
        # self.dbg_exceptionbp('all', True)
        pass
        return

    def collect_incoming_data(self, data):
        self.ibuffer.append(data)
        return

    def found_terminator(self):
        data = b''.join(self.ibuffer).decode()
        if self.reading_headers:
            # ヘッダの受け取り.
            headers = parse_headers(data)
            clen = int(headers['Content-Length'])
            if clen > 0:
                # 長さの指定があったので受け取る.
                self.set_terminator(clen)
                self.reading_headers = False
            else:
                # 長さの指定がなかったので、次のヘッダを待つ.
                self.set_terminator(b'\r\n\r\n')
                self.reading_headers = True
            self.ibuffer = []

        else:
            # ボディの受け取り.
            self.set_terminator(b'\r\n\r\n')
            self.reading_headers = True
            self.ibuffer = []
            self._handle_resp(json.loads(data))
        return

    #-----------------------------------------------------------------------
    #   utils
    #-----------------------------------------------------------------------
    def loop(self):
        asyncore.loop()

    def send_req(self, req):
        """debugger へ request を送信する."""

        req['type'] = 'request'
        msg = json.dumps(req).encode()
        cont = b'Content-Length:' + str(len(msg)).encode() + b"\r\n\r\n" + msg

        # TODO: slepp は下記のエラーへの暫定対応なので、まともな方法を調べる.
        # ----
        # "deque index out of range"
        # source line: "del self.producer_fifo[0]"
        # at /usr/lib/python3.3/asynchat.py:254
        time.sleep(0.05)
        self.push(cont)
        return

    #-----------------------------------------------------------------------
    #   commands for Node.js debugger
    #-----------------------------------------------------------------------

    def dbg_disconnect(self):
        req = {
                'command': 'disconnect'
                }
        self.send_req(req)
        return

    def dbg_continue(self, step=None, count=1):
        """debugger へ continue をリクエスト.

        step は None または 'in' 'out' 'next' いずれかの文字列とし、
        ステップインなどの送信もこのメソッドで行う.
        """
        req = {
                'command': 'continue',
                'arguments': {
                    'stepaction': step,
                    'stepcount': count
                    }
                }
        if step is None:
            del req['arguments']

        self.send_req(req)
        return

    def dbg_setbp(self, name, lnum, enabled=True, columnNumber=0, \
            condition=None, ignoreCount=0):
        req = {
                'command': 'setbreakpoint',
                'arguments': {
                    'type': 'script',
                    'target': name,
                    'line': int(lnum) - 1,
                    'column': columnNumber,
                    'enabled': enabled,
                    'condition': condition,
                    'ignoreCount': ignoreCount
                    }
                }

        self.send_req(req)
        return

    def dbg_clearbp(self, bp_id):
        req = { 
                'command': 'clearbreakpoint',
                'arguments': { 
                    'breakpoint': bp_id
                    }
                }
        self.send_req(req)
        return

    def dbg_changebp(self, bp_id, enabled, condition=None, ignoreCount=0):
        req = { 
                "command": "changebreakpoint",
                "arguments": {
                    "breakpoint": bp_id,
                    "enabled": enabled,
                    'condition': condition,
                    'ignoreCount': ignoreCount
                    }
                }
        self.send_req(req)
        return

    def dbg_backtrace(self):
        req = {
                'command': 'backtrace'
                }
        self.send_req(req)
        return

    def dbg_evaluate(self, expression, frame=0, context=None):

        req = {
                'command': 'evaluate',
                'arguments': {
                    'expression': expression,
                    'frame': frame,
                    'global': frame == None,
                    'disable_break': True,
                    'additional_context': context,
                    'maxStringLength': 100000
                    }
                }
        self.send_req(req)
        return

    def dbg_exceptionbp(self, type, enabled):
        req = {
                'command': 'setexceptionbreak',
                'arguments': {
                    'type': type,
                    'enabled': enabled
                    }
                }
        self.send_req(req)
        return

    def dbg_scripts(self):
        self.send_req({ 'command': 'scripts' })
