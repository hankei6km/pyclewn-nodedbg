# vi:set ts=8 sts=4 sw=4 et tw=80:
#
# Copyright (C) 2007 Xavier de Gaye.
# Copyright (C) 2013 hankei6km
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program (see the file COPYING); if not, write to the
# Free Software Foundation, Inc.,
# 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA
#

"""Pyclewn 付属の Simple class(simple.py) を Node.js debugger 対応にしたもの.

"""

import os
import sys
import threading
import functools
import queue

from . import (misc, debugger)

from .nodeclient import NodeClient
from .nodeutils import (obj_to_print, BreakPoints, Scripts)

# set the logging methods
(critical, error, warning, info, debug) = misc.logmethods('nodedbg')
Unused = critical
Unused = error
Unused = warning
Unused = debug

# ブレイクポイントの管理
# Debugger クラスはデバッグ対象が起動するマイにインスタンスが作成されるので、
# グローバルにした(んだけどいいのか?)
bps = BreakPoints()

# list of key mappings, used to build the .pyclewn_keys.simple file
#     key : (mapping, comment)
MAPKEYS = {
    'C-B': ('break ${fname}:${lnum}',
                'set breakpoint at current line'),
    'C-E': ('clear ${fname}:${lnum}',
                'clear breakpoint at current line'),
    'C-P': ('print ${text}',
                'print value of selection at mouse position'),
    'C-Z': ('interrupt',
                'interrupt the execution of the target'),
    'S-C': ('continue',),
    'S-Q': ('quit',),
    'S-S': ('step',),
}

# list of the nodedbg commands mapped to vim user commands C<command>
NODEDBG_CMDS = {
    'break': None,   # file name completion
    'continue': (),
    'disable': (),
    'enable': (),
    #'interrupt': (),
    'print': (),
    'quit': (),
    'step': (),

    'stepin': (),
    'stepout': (),
    # TODO: レスポンスの整形にまだ対応できてないのでコメントアウト
    # 'backtrace': (),
    'attach': (),
    'dettach': ()
}

class NodeTarget(threading.Thread):
    """Node.js debugger target in another thread."""

    def __init__(self, daemon):
        """Constructor."""
        threading.Thread.__init__(self)
        self.daemon = daemon

        self.bp_dict = {}
        self.bp_que = queue.Queue()

        self.closed = False
        self.running = False

        # do not print on stdout when running unittests
        self.testrun = functools.reduce(lambda x, y: x or (y == 'unittest'),
                                        [False] + list(sys.modules.keys()))
        self._client = NodeClient(self.handle_resp)
        self._client.connect_start()

    def close(self):
        """Close the target."""
        self._client.dbg_disconnect()
        self._client.close_when_done()
        self.closed = True

    def add_bp(self, bp_id, name, lnum):
        """Add breakpoint."""
        k = name + ':' + str(lnum)
        if k in self.bp_dict:
            pass
        else:
            self.bp_dict[k] = -1 # 重複しての追加がないようにダミーのキーを登録
            self._client.dbg_setbp(name, lnum)
        return True

    def delete_bp(self, name, lnum):
        """Delete breakpoint."""
        k = name + ':' + str(lnum)
        if k in self.bp_dict:
            bp_id = self.bp_dict[k]
            del self.bp_dict[k]
            self._client.dbg_clearbp(bp_id)
        return True

    def update_bp(self, bp_id, enabled):
        """Update breakpoint."""
        self._client.dbg_changebp(bp_id, not enabled)
        return True

    def run_continue(self):
        """Start or continue the debuggee."""
        #if self.running:
        #    return False
        self.running = True
        self._client.dbg_continue()
        return True

    def step(self):
        """Do a single step."""
        #if self.running:
        #    return False
        self._client.dbg_continue('next', 1)
        return True

    def stepin(self):
        """Do a single stepin."""
        self._client.dbg_continue('in', 1)
        return True

    def stepout(self):
        """Do a single stepin."""
        self._client.dbg_continue('out', 1)
        return True

    def backtrace(self):
        """Print a value."""
        if self.running:
            return False
        self._client.dbg_backtrace()
        return True

    def print(self, args):
        """Print a value."""
        #if self.running:
        #    return False
        self._client.dbg_evaluate(args)
        return True

    def scripts(self):
        """get loaded scripts list."""
        self._client.dbg_scripts()
        return True

    def __repr__(self):
        """Return the target representation."""
        return "Target: {'running': %s, 'closed': %s}" % (self.running,
                                                                self.closed)

    def run(self):
        """Run the target."""
        self._client.loop()

        item = {}
        item['type'] = 'close'
        self.bp_que.put(item)

        self.running = False

    def handle_resp(self, data):
        """client(node.js の debugger) からのレスポンスを処理する.

        """
        if data['type'] == 'event':
            if data['event'] == 'break':
                item = {}
                item['type'] = 'break'
                item['name'] = data['body']['script']['name'] 
                item['lnum'] =data['body']['sourceLine'] + 1 
                self.running = False
                self.bp_que.put(item)
            if data['event'] == 'exception':
                item = {}
                item['type'] = 'break'
                item['name'] = data['body']['script']['name'] 
                item['lnum'] =data['body']['sourceLine'] + 1 
                self.running = False
                self.bp_que.put(item)
                item = {}
                item['type'] = 'print'
                item['text'] = data['body']['exception']['text']
                self.bp_que.put(item)

        elif data['type'] == 'response':
            if data['command'] == 'disconnect':
                item = {}
                item['type'] = 'close'
                self.bp_que.put(item)
            elif data['command'] == 'setbreakpoint':
                item = {}
                item['type'] = 'setbreakpoint'
                name = data['body']['script_name']
                lnum = data['body']['actual_locations'][0]['line'] + 1 
                bp_id = data['body']['breakpoint']
                item['name'] = name
                item['lnum'] = lnum
                item['bp_id'] = bp_id
                self.bp_que.put(item)
                # target 側でもid を保持しておく.
                self.bp_dict[name + ':' + str(lnum)] = bp_id
            elif data['command'] == 'backtrace':
                item = {}
                item['type'] = 'print'
                item['text'] = '\n'
                for i in data['body']['frames']:
                    item['text'] = item['text'] + i['text'] + '\n'
                self.bp_que.put(item)
            elif data['command'] == 'evaluate':
                item = {}
                item['type'] = 'print'
                if data['success']:
                    item['text'] = obj_to_print(data)
                else:
                    item['text'] = data['message']
                self.bp_que.put(item)
            elif data['command'] == 'scripts':
                item = {}
                item['type'] = 'scripts'
                item['body'] = data['body']
                self.bp_que.put(item)
        return

class NodeDbg(debugger.Debugger):
    def __init__(self, *args):
        """Constructor."""
        debugger.Debugger.__init__(self, *args)
        self.pyclewn_cmds.update(
            {
                # 'dbgvar': (),
                # 'delvar': (),
                'sigint': (),
                'symcompletion': (),
            })
        self.cmds.update(NODEDBG_CMDS)
        self.mapkeys.update(MAPKEYS)
        self.bp_id = 0
        self._bp_resp = {}
        self._bpgo_que =queue.Queue() 
        self._scripts = Scripts()
        self.inferior = None

    def start(self):
        """Start the debugger."""
        self.console_print('\n')
        self.print_prompt()

        # start the node.js debuggee
        if self.inferior is None:
            self.inferior = NodeTarget(self.options.daemon)
            self.inferior.start()
            self.inferior.scripts()
            self.timer(self.myjob, debugger.LOOP_TIMEOUT)

    def close(self):
        """Close the debugger."""
        debugger.Debugger.close(self)

        # close the debuggee
        if self.inferior is not None:
            self.inferior.close()
            self.inferior = None

    def remove_all(self):
        debugger.Debugger.remove_all(self)
        self.bp_id = 0
        # bps.remove_all()
        self._bp_resp = {}

    def move_frame(self, show):
        """Show the frame sign or hide it when show is False.

        The frame sign is displayed from the first line (lnum 1), to the
        first enabled breakpoint in the stepping buffer.

        """
        if show:
            script_name = self._bp_resp['name']
            if script_name is not None:
                if os.path.isabs(script_name):
                    self.show_frame(self._bp_resp['name'], \
                            self._bp_resp['lnum'])
                else:
                    self.console_print('Break in '+ script_name +'.\n')
        else:
            # hide frame
            self.show_frame()

    def myjob(self):
        if self.inferior is not None:
            bp_que = self.inferior.bp_que
            while not bp_que.empty():
                item = bp_que.get()
                if item['type'] == 'close':
                    self.console_print('Node.js debugger connection closed.\n')
                    self.print_prompt()
                    self.move_frame(False)
                    self.inferior = None
                    bps.standby_all()
                    self.remove_all()
                    self.closed = True
                elif item['type'] == 'setbreakpoint':
                    self.add_bp(item['bp_id'], item['name'], item['lnum'])
                    bps.add(item['bp_id'], item['name'], str(item['lnum']))
                    self.console_print('Breakpoint %d at file %s, line %d.\n' % \
                            (item['bp_id'], item['name'], item['lnum']))
                elif item['type'] == 'break':
                    self._bp_resp = item
                    self.move_frame(True)
                elif item['type'] == 'print':
                    self.console_print(item['text'] + '\n')
                    self.print_prompt()
                elif item['type'] == 'scripts':
                    self._scripts.set_scripts(item['body'])
                    bplist = bps.get_standby_bps(self._scripts)
                    if len(bplist) > 0:
                        for bp in bplist:
                            bps.clear_standby(bp['name'], bp['lnum'])
                            self.inferior.add_bp(bp['bp_id'], bp['name'], bp['lnum'])
                    else:
                        while not self._bpgo_que.empty():
                            fn = self._bpgo_que.get()
                            fn()
                            self._bpgo_que.task_done()


                bp_que.task_done()

        if self.closed == False:
            self.inferior.scripts()
            self.timer(self.myjob, debugger.LOOP_TIMEOUT + 0.1)


    #-----------------------------------------------------------------------
    #   commands
    #-----------------------------------------------------------------------

    def pre_cmd(self, cmd, args):
        """The method called before each invocation of a 'cmd_xxx' method."""
        if args:
            cmd = '%s %s' % (cmd, args)
        self.console_print('%s\n', cmd)

        # turn off all hilited variables

    def post_cmd(self, cmd, args):
        """The method called after each invocation of a 'cmd_xxx' method."""
        unused = cmd
        unused = args
        # to preserve window order appearance, all the writing to the
        # console must be done before starting to handle the (clewn)_dbgvar
        # buffer when processing Cdbgvar
        # update the vim debugger variable buffer with the variables values

    def default_cmd_processing(self, cmd, args):
        """Process any command whose cmd_xxx method does not exist."""
        unused = cmd
        unused = args
        self.console_print('Command ignored.\n')
        self.print_prompt()

    def cmd_attach(self, cmd, args):
        """ Attach to Node.js debugger."""
        unused = cmd

        if self.inferior is None:
            self.inferior = NodeTarget(self.options.daemon)
            self.inferior.start()
        else:
            self.console_print('The inferior progam was attached.\n')
        self.print_prompt()

    def cmd_dettach(self, cmd, args):
        """ Dettach from Node.js debugger."""
        unused = cmd

        if self.inferior is None:
            self.console_print('The inferior progam was not attached.\n')
        else:
            self.inferior.close()
        self.print_prompt()

    def cmd_break(self, cmd, args):
        """Set a breakpoint at a specified line.

        The required argument of the vim user command is 'fname:lnum'.

        """
        unused = cmd

        name, lnum = debugger.name_lnum(args)
        if name:
            self.bp_id += 1
            # 実際の位置はセットしてみないとわからないので、
            # ここでは追加の設定のみ行い、
            # アノテーションはレスポンスを受け取ったときにセットする.
            # TODO: ロードされてないスクリプトの場合は、
            # 実際にロードされるまでレスポンスがないので、
            # アノテーションは表示されないので、なにか対応を.
            bps.add_standby(self.bp_id, name, lnum)
            self.inferior.scripts()
        else:
            self.console_print('Invalid arguments.\n')

        self.print_prompt()

    def cmd_clear(self, cmd, args):
        """ Clear breakpoint at a specified line.

        The required argument of the vim user command is 'fname:lnum'.

        """
        unused = cmd
        result = 'Invalid arguments.\n'

        name, lnum = debugger.name_lnum(args)
        if name:
            bp_id = bps.get_bp_id(name, lnum)
            if bp_id is not None:
                bps.remove(name, lnum)
                self.delete_bp(bp_id)
                self.inferior.delete_bp(name, lnum)
                result = 'Clear Breakpoint %d at file %s, line %d.\n' % \
                                                (bp_id, name, lnum)

        self.console_print(result)
        self.print_prompt()

    def set_bpstate(self, cmd, args, enable):
        """Change the state of one breakpoint."""
        unused = cmd
        args = args.split()
        result = 'Invalid arguments.\n'

        # accept only one argument, for now
        if len(args) == 1:
            result = '"%s" not found.\n' % args[0]
            name, lnum = bps.get_name_lnum(args[0])
            if name is not None:
                self.update_bp(args[0], not enable)
                self.inferior.update_bp(args[0], not enable)
                result = ''

        self.console_print(result)
        self.print_prompt()

    def cmd_disable(self, cmd, args):
        """Disable one breakpoint.

        The required argument of the vim user command is the breakpoint number.

        """
        self.set_bpstate(cmd, args, False)

    def cmd_enable(self, cmd, args):
        """Enable one breakpoint.

        The required argument of the vim user command is the breakpoint number.

        """
        self.set_bpstate(cmd, args, True)

    def cmd_step(self, *args):
        """Step program until it reaches a different source line."""
        unused = args
        assert self.inferior is not None
        self.inferior.step()
        self.move_frame(False)
        self.print_prompt()

    def cmd_stepin(self, *args):
        """Step into function."""
        unused = args
        assert self.inferior is not None
        self.inferior.stepin()
        self.move_frame(False)
        self.print_prompt()

    def cmd_stepout(self, *args):
        """Step out current function."""
        unused = args
        assert self.inferior is not None
        self.inferior.stepout()
        self.move_frame(False)
        self.print_prompt()

    def cmd_continue(self, *args):
        """Continue the program being debugged, also used to start the program."""
        unused = args
        assert self.inferior is not None
        #if not self.inferior.run_continue():
        #    self.console_print('The inferior progam is running.\n')
        self._bpgo_que.put(self.inferior.run_continue)
        self.inferior.scripts()
        self.print_prompt()
        self.move_frame(False)

    def cmd_backtrace(self, *args):
        """Print backtrace."""
        unused = args
        assert self.inferior is not None
        self.inferior.backtrace()
        self.print_prompt()

    def cmd_print(self, cmd, args):
        """Print a value."""
        unused = cmd
        if args:
            self.inferior.print(args)
        else:
            self.console_print('Invalid arguments.\n')
            self.print_prompt()

    def cmd_quit(self, *args):
        """Quit the current nodedbg session."""
        unused = args
        if self.inferior is not None:
            self.close()
        self.console_print('Netbeans connection closed.\n')
        self.console_flush()
        self.print_prompt()
        self.netbeans_detach()

    def cmd_sigint(self, *args):
        """Send a <C-C> character to the debugger (not implemented)."""
        unused = self
        unused = args
        self.console_print('Not implemented.\n')
        self.print_prompt()

    def cmd_symcompletion(self, *args):
        """Populate the break and clear commands with symbols completion (not implemented)."""
        unused = self
        unused = args
        self.console_print('Not implemented.\n')
        self.print_prompt()
