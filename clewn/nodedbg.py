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
import traceback
import threading
import functools
import queue

from . import (misc, debugger)

try:
    from collections import OrderedDict
except ImportError:
    from .misc import OrderedDict

from .nodeclient import NodeClient
from .nodeutils import (obj_to_print, obj_to_properties, BreakPoints, Scripts)

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
    'S-X': ('foldvar ${lnum}',
                'expand/collapse a watched variable'),
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

    def lookup(self, handles):
        self._client.lookup(handles)
        return True

    def frame(self):
        """get selected frame."""
        self._client.dbg_frame()
        return True

    def scope(self, scopeNumber):
        """get scope on selected frame."""
        self._client.dbg_scope(scopeNumber)
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
        try:
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
                    print(data['body']['frames'][0])
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
                elif data['command'] == 'lookup':
                    if data['success']:
                        for body in data['body']:
                            item = {}
                            item['type'] = 'properties'
                            item['handle'] =data['body'][body]['handle']
                            item['properties'] = obj_to_properties(data,
                                    data['body'][body], item['handle'])
                            self.bp_que.put(item)
                elif data['command'] == 'frame':
                    item = {}
                    item['type'] = 'frame'
                    if data['success']:
                        item['scopes'] = data['body']['scopes']
                        self.bp_que.put(item)
                        for scope in data['body']['scopes']:
                            self.scope(scope['index'])
                elif data['command'] == 'scope':
                    item = {}
                    item['type'] = 'scope'
                    if data['success']:
                        item['body'] = data['body']
                    self.bp_que.put(item)
        except:
            #traceback.print_tb(sys.exc_info()[2])
            item = {}
            item['type'] = 'print'
            item['text'] = '\nException in nodedbg(handle_resp)\n'
            item['text'] = item['text'] + '%s\n%s\n\n' % sys.exc_info()[:2]
            item['text'] = item['text'] + traceback.format_exc()
            self.bp_que.put(item)
        return

class NodeVar:
    """ Node var class."""
    def __init__(self):
        """Constructor."""
        self.dirty = True

        self.scopes = []
        self.scope_lookup = {}

        self.prev_scopes = []

    def scopes_equal(self, scopes):
        """ 指定された scopes が、保持している scopes と同じか?
        ただし、ここでは厳密には区別できない(する方法が不明)ので、
        deep equal ではない. """

        ret = True
        if len(self.scopes) != len(scopes):
            ret = False
        else:
            for scope in scopes:
                if self.scopes[scope['index']]['type'] != scope['type']:
                    ret = False

        return ret

    def set_scopes(self, scopes):

        if self.scopes_equal(scopes):
            # 前回と同じ scopes の可能性が高いので、
            # 退避しておく.
            self.prev_scopes = self.scopes
        else:
            # 前回と異なる scopes の可能性が高いので、
            # 退避していた情報は破棄.
            self.prev_scopes = []

        self.scopes = [0] * len(scopes);
        for scope in scopes:
            lbl = ''
            expanded = False
            if scope['type'] == 0:
                lbl = 'Global'
            elif scope['type'] == 1:
                lbl = 'Local'
                expanded = True
            elif scope['type'] == 2:
                lbl = 'With'
            elif scope['type'] == 3:
                lbl = 'Closure'
                expanded = True
            elif scope['type'] == 4:
                lbl = 'Catch'
            item = {
                    'type': scope['type'],
                    'lbl': lbl,
                    'expanded': expanded,
                    'standby': True,
                    'properties': []
                    }
            self.scopes[scope['index']] = item

        if len(self.prev_scopes):
            # 退避しておいた情報から、一部の情報を復元する.
            index = 0
            for scope in self.scopes:
                scope['expanded'] = self.prev_scopes[index]['expanded']
                index = index + 1

        self.dirty = True

        return

    def restore_prev_scopes(self):
        """ 退避していた scopes を戻す. 

        本来必要ない処理だが、scope が存在しないエラーからのリカバリー用.
        """
        self.scopes = self.prev_scopes

        return

    def move_properties_array_to_ordered_dict(self, array_p, dict_p):

        for prop in array_p:
            item = {'name': prop['name']}
            if not ('value' in prop['value']):
                item['expanded'] = False
                item['properties'] = []
            item['value'] = prop['value']

            dict_p[item['name']] = item

        return

    def properties_equal(self, p1, p2):
        """ properties の比較.
        個数と、それぞれの name と value/type で比較."""

        ret = True

        if len(p1) != len(p2):
            ret = False
        else:
            for p in p1:
                if not (p in p2):
                    ret = False
                else:
                   if p1[p]['value']['type'] != p2[p]['value']['type']:
                       ret = False

        return ret

    def set_scope_props(self, index, properties):
        self.scopes[index]['properties'] = OrderedDict();

        self.move_properties_array_to_ordered_dict(properties, \
                self.scopes[index]['properties']
                )

        if len(self.prev_scopes) > index:
            if self.properties_equal( \
                    self.scopes[index]['properties'], \
                    self.prev_scopes[index]['properties']
                    ):
                # 前回と同じ properties(scope) の可能性が高いので、
                # 部分的に情報を復元する.
                # なお、復元された情報は value が古いままなので、
                # このメソッドの呼び出し元で、
                # get_lookup_list メソッドから lookup すべき handle 一覧を取得し
                # 再度 lookup を行う必要がある.
                for p in self.scopes[index]['properties']:
                    cur = self.scopes[index]['properties'][p]
                    prev = self.prev_scopes[index]['properties'][p]
                    if 'expanded' in prev:
                        cur['expanded'] = prev['expanded']
                        cur['properties'] = prev['properties']

        self.scopes[index]['standby'] = False;

        self.dirty = True

        return

    def get_lookup_list(self):
        """Objectの展開などで lookup していた handle のリスト取得."""
        ret = []

        # ref が変わっているので、index と name から再取得.

        prev_lookup = self.scope_lookup
        self.scope_lookup = {}
        for handle in prev_lookup:
            tgt = self.get_tgt_item_from_names( \
                    prev_lookup[handle]['index'], \
                    prev_lookup[handle]['name'] \
                    )
            if 'value' in tgt:
                self.scope_lookup[tgt['value']['ref']] = {\
                        'index': prev_lookup[handle]['index'], \
                        'name': prev_lookup[handle]['name']
                        }
                ret.append(tgt['value']['ref'])

        return ret

    def set_properties_from_handle(self, handle, properties):

        tgt = self.get_tgt_item_from_names( \
                self.scope_lookup[handle]['index'],\
                self.scope_lookup[handle]['name']
                )
        tgt['properties'] = OrderedDict()

        self.move_properties_array_to_ordered_dict(properties, \
                tgt['properties']
                )

        self.dirty = True

        return

    def is_standby(self):
        ret = False
        for scope in self.scopes:
            if scope['standby']:
                ret = True

        return ret

    def get_tgl_lbl(self, item):
        ret = '   '
        if 'expanded' in item:
            if item['expanded']:
                ret = '[-]'
            else:
                ret = '[+]'
        
        return ret

    def get_value_lbl(self, item):
        ret = ''

        if 'value' in item['value']:
            ret = item['value']['value']
        else:
            if 'className' in item['value']:
                ret = '<%s>' % (item['value']['className'])
            else:
                ret = '<%s>' % (item['value']['type'])

        return ret

    def scope_var_str(self, properties, prev_properties, depth):
        varstr = ''

        for name in properties:
            var = properties[name]
            prev_var = {'properties':{}, 'value': {'type':''}}
            if name in prev_properties:
                prev_var = prev_properties[name]
            name = var['name']
            value = self.get_value_lbl(var)
            hilite = '='
            if 'value' in var['value']:
                if 'value' in prev_var['value']:
                    if var['value']['value'] != prev_var['value']['value']:
                        hilite = '*'
                else:
                    hilite = '*'
            else:
                if not 'value' in prev_var['value']:
                    if var['value']['type'] != prev_var['value']['type']:
                        hilite = '*'
                else:
                    hilite = '*'
            tgl_lbl = self.get_tgl_lbl(var)
            varstr += ' ' * depth + '%s %s ={%s} %s\n' % (tgl_lbl, name, hilite, value)
            if 'expanded' in var and var['expanded']:
                varstr = varstr + \
                        self.scope_var_str( \
                                var['properties'], \
                                prev_var['properties'], \
                                depth + 1 \
                                )

        return varstr

    def __str__(self):
        varstr = ''

        index = 0
        for scope in self.scopes:
            prev_scope = {'properties':{}}
            if len(self.prev_scopes) > index:
                prev_scope = self.prev_scopes[index]

            tgl_lbl = self.get_tgl_lbl(scope)
            if tgl_lbl:
                varstr = varstr + '%s %s\n' % (tgl_lbl, scope['lbl'])
                if scope['expanded']:
                    varstr = varstr + \
                            self.scope_var_str( \
                                    scope['properties'], \
                                    prev_scope['properties'], \
                                    1 \
                                    )
            index = index + 1

        self.dirty = False

        return varstr

    def get_tgt_item_from_names(self, index, name, type='scopes'):

        if type =='scopes':
            ret = self.scopes[index]
        else:
            ret = self.prev_scopes[index]

        for n in name:
            if n in ret['properties']:
                ret = ret['properties'][n]
            else:
                ret = {}
                break

        return ret

    def get_properties_lines(self, index, properties, pnames):
        lines = []
        for name in properties:
            var = properties[name]
            line = {
                    'name': pnames + [var['name']],
                    'index': index
                    }
            if 'expanded' in var:
                line['expanded'] = var['expanded']

            lines.append(line)

            if 'expanded' in var and var['expanded']:
                rlines = self.get_properties_lines(index, var['properties'], \
                        line['name'])
                lines.extend(rlines)

        return lines

    def foldvar(self, lnum):
        ret = -1

        lines = []
        index = 0

        for scope in self.scopes:
            line = {
                    'root': True,
                    'index': index
                    }
            line['expanded'] = scope['expanded']
            lines.append(line)
            if scope['expanded']:
                lines.extend(self.get_properties_lines(index, scope['properties'], []))
            index = index + 1

        line = lines[lnum-1]
        if 'root' in line:
            self.scopes[line['index']]['expanded'] = \
                not self.scopes[line['index']]['expanded']
        else:
            tgt = self.get_tgt_item_from_names(line['index'], line['name'])
            if 'expanded' in tgt:
                tgt['expanded'] = not tgt['expanded']
            ret = tgt['value']['ref']
            self.scope_lookup[ret] = {
                    'index': line['index'],
                    'name': line['name']
                    }

        return ret

class NodeDbg(debugger.Debugger):
    def __init__(self, *args):
        """Constructor."""
        debugger.Debugger.__init__(self, *args)
        self.pyclewn_cmds.update(
            {
                'dbgvar': (),
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

        self.varobj = NodeVar()

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
        self.inferior.frame();
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
                elif item['type'] == 'properties':
                    self.varobj.set_properties_from_handle(item['handle'], item['properties'])
                    if self.varobj.is_standby() == False:
                        self.update_dbgvarbuf(self.varobj.__str__,
                                self.varobj.dirty)
                elif item['type'] == 'frame':
                    if 'scopes' in item:
                        self.varobj.set_scopes(item['scopes'])
                    else:
                        # FIXME: frame が存在しない'No framse)というエラーの対応.
                        # エラーが発生しないようにできないか?
                        self.inferior.frame();
                elif item['type'] == 'scope':
                    if 'body' in item:
                        self.varobj.set_scope_props(item['body']['index'], \
                            item['body']['object']['properties']);
                        if self.varobj.is_standby() == False:
                            handles = self.varobj.get_lookup_list()
                            self.inferior.lookup(handles)
                            self.update_dbgvarbuf(self.varobj.__str__,
                                    self.varobj.dirty)
                    else:
                        # FIXME: scope が存在しないというエラー対応.
                        # frame コマンドから取得した scope なので存在しないとい
                        # うことはないと思うのだが、タイミング依存でなにかあるの
                        # か?
                        self.varobj.restore_prev_scopes()
                        self.inferior.frame();

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
        #self.inferior.frame();
        #self.update_dbgvarbuf(self.varobj.__str__, True)

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
        self.print_prompt()

    def cmd_stepin(self, *args):
        """Step into function."""
        unused = args
        assert self.inferior is not None
        self.inferior.stepin()
        self.print_prompt()

    def cmd_stepout(self, *args):
        """Step out current function."""
        unused = args
        assert self.inferior is not None
        self.inferior.stepout()
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

    def cmd_foldvar(self, cmd, args):
        """Collapse/expand a variable from the debugger variable buffer."""
        unused = cmd
        args = args.split()
        if len(args) != 1:
            self.console_print('Invalid arguments.')
        else:
            try:
                lnum = int(args[0])
                ref = self.varobj.foldvar(lnum)
                if ref < 0:
                    self.update_dbgvarbuf(self.varobj.__str__, True)
                else:
                    self.inferior.lookup([ref])
            except ValueError:
                self.console_print('Not a line number.')


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
