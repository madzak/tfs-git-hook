# Copyright (C) 2008  Jack Moffitt jack@metajack.im, https://github.com/metajack/notify-webhook
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

def get_revisions(old, new):
    git = subprocess.Popen([r"git", 'rev-list', '--pretty=medium', r'%s..%s' % (old, new)], stdout=subprocess.PIPE)
    sections = git.stdout.read().split('\n\n')[:-1]

    revisions = []
    s = 0
    while s < len(sections):
    lines = sections[s].split('\n')

    # first line is 'commit HASH\n'
    props = {'id': lines[0].strip().split(' ')[1]}

    # read the header
    for l in lines[1:]:
        key, val = l.split(' ', 1)
        props[key[:-1].lower()] = val.strip()

    # read the commit message
    props['message'] = sections[s+1].strip()

    # use github time format
    basetime = datetime.strptime(props['date'][:-6], "%a %b %d %H:%M:%S %Y")
    tzstr = props['date'][-5:]
    props['date'] = basetime.strftime('%Y-%m-%dT%H:%M:%S') + tzstr

    # split up author
    m = EMAIL_RE.match(props['author'])
    if m:
        props['name'] = m.group(1)
        props['email'] = m.group(2)
    else:
        props['name'] = 'unknown'
        props['email'] = 'unknown'
    del props['author']

    s += 2
    revisions.append(props)

    return revisions
