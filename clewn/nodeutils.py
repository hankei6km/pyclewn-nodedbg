# vi:set ts=8 sts=4 sw=4 et tw=80:
#
# @author hankei6km
# @copyright (c) 2013 hankei6km
# @license MIT License (http://opensource.org/licenses/mit-license.php)
#

def parse_headers(resp):
    """ Node.js のレスポンスのヘッダをパース.

    TODO: とりあえずで作ったので、まともな方法を考えること.
    """

    ret = {}
    header_lines = resp.split('\r\n')
    for line in header_lines:
        k, v = line.split(':')
        ret[k] = v

    return ret

def _obj_to_print(className, properties, refs):
    """ プロパティを持っている場合の変換 ."""

    ret = ''
    for p in properties:
        for r in refs:
            if p['ref'] == r['handle']:
                text = r['text']
                if r['type'] == 'object':
                    if r['className'] == 'Array':
                        text = '#<Array>'
                    else:
                        text = '#<Object>'
                elif r['type'] == 'function':
                    text = '#<Function>'
                ret = ret + ' ' + str(p['name']) + ': ' + text + '\n'
                break
    if className == 'Array':
        ret = '[\n' + ret + ']'
    else:
        ret = '{\n' + ret + '}'
    return ret

def obj_to_print(data):
    """ Node.js のオブジェクトを表示用文字列に変換."""

    ret = ''
    if data['body']['type'] == 'object':
        ret = _obj_to_print(
                data['body']['className'],
                data['body']['properties'],
                data['refs'])
    elif data['body']['type'] == 'function':
        ret  = '#<Function>'
    else:
        ret = data['body']['text']
    return ret

class BreakPoints():
    def __init__(self):
        self.bp_dict = {}

    def _get_key(self, name, lnum):
        return str(lnum) + ':' + name

    def _get_name_lnum_from_key(self, key):
        name, lnum = key.split(':', 2)
        return name,  lnum

    def add(self, bp_id, name, lnum):
        self.bp_dict[self._get_key(name, lnum)] = {'bp_id': bp_id}
        return

    def remove(self, bp_id):
        name, lnum = self.get_name_lnum(bp_id)
        if name is not None:
            del self.bp_dict[self._get_key(name, lnum)]

    def remove(self, name, lnum):
        del self.bp_dict[self._get_key(name, lnum)]

    def remove_all(self):
        self.bp_dict = {}
        return

    def get_bp_id(self, name, lnum):
        return self.bp_dict[self._get_key(name, lnum)]['bp_id']

    def get_name_lnum(self, bp_id):
        """ bp_id から name と lnum を取得 """
        key = None
        for k, v in self.bp_dict.items():
            if str(v['bp_id']) == str(bp_id):
                key = k
                break
        if key is not None:
            return self._get_name_lnum_from_key(key)
        else:
            return None, None
    
class Scripts():
    """ ロード済スクリプトの一覧 """
    def __init__(self):
        self.scripts_dict = {}

    def remove_all(self):
        self.scripts_dict = {}
        return

    def set_scripts(self, scripts_resp_body):
        self.remove_all()
        for i in scripts_resp_body:
            if 'name' in i:
                self.scripts_dict[i['name']] ={'type': i['type']}
        return

    def exist(self, name):
        if self.scripts_dict[name] is not None:
            return True
        else:
            return False
