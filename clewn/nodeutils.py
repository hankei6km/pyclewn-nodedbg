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

