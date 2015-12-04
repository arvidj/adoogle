import sqlite3
import sys
import re
# from sqlobject.sqlbuilder import *

from colorama import init, Fore, Back, Style
from termcolor import colored, cprint

from entity_kinds import *

verbose = True
activate_colors = True


def is_function_kind(k):
    return k in function_kinds

def parse_query(query_string):
    def m_strip(ls):
        return map(str.strip, ls)

    # none means any
    query = {
        'name': None,
        'type': None, # type of a constant, variable, etc
        'kind': None, # gnat inspect internal?
        'signature': None, # can be a list of types
    }

    # check for kind
    m = re.search("^\((.*)\)(.*)", query_string)
    if m:
        kind_str = m.group(1)
        if kind_str == 'fun':
            query['kind'] = function_kinds
        elif kind_str == 'pkt':
            query['kind'] = package_kinds
        else:
            query['kind'] = kind_str.split(',')
        query_string = m.group(2)

    # check signature
    (query['name'], _, rest) = m_strip(query_string.partition(':'))
    if '->' in rest:
        # should do intersection with existing kinds
        query['kind'] = function_kinds
        query['signature'] = m_strip(rest.split('->'))
    elif rest != '':
        # if len(rest) == 1:
        #     query['kind'] = rest
        # else:
        query['type'] = rest

    if verbose:
        print("Parsed query object: ", query)

    return query

def query_builder(query_string):
    query = parse_query(query_string)
    sql_query = {
        'from': 'entities',
        'where': []
    }
    if query['name'] is not None:
        sql_query['where'].append("entities.name LIKE '%{0}%'".format(query['name']))
    if query['kind'] is not None and len(query['kind']) > 0:
        sql_query['where'].append("entities.kind in ({0})".format(','.join(["'%s'" % k for k in query['kind']])))
    if query['type'] is not None:
        sql_query['from'] += (" INNER JOIN e2e ON (e2e.kind = 11 AND e2e.fromEntity = entities.id AND e2e.toEntity IN " +
                              " (SELECT id FROM entities WHERE name = '{0}'))".format(query['type']))
    if query['signature'] is not None:
        # print(list(query['signature']))
        # for i, p in query['signature'].items():
        #     sql_query['from'] += (
        #         " LEFT JOIN e2e as e2e_param_{0} ON (e2e_param_{0}.fromEntity = entities.id AND e2e_param_{0}.kind IN (12,13,14,15))"
        #         " LEFT JOIN entities as e_param_{0} ON (e_param_{0}.id = e2e_param_{0}.toEntity)"
        #         " LEFT JOIN e2e as e2e_type_{0} ON (e2e.fromEntity = entities.id AND e2e_type_{0}.kind = 11)"
        #         " LEFT JOIN entities as e_type_{0} ON (e_type_{0}.id = e2e_type_{0}.toEntity)"
        #     ).format(i)
        #     sql_query['where'].append("e_param_{}.name like '{}".format(i, p))

        pass


    sql_query['where'] = ' AND '.join(sql_query['where'])
    query_string = "SELECT * FROM {from} WHERE {where} GROUP BY entities.id".format(**sql_query)

    if verbose:
        print("Built query string: ", query_string)

    return query_string

color_scheme = {
    'entity_kind' : ('magenta', []),
    'type' : ('magenta', []),
    'param_kind' : ('green', [])
}

def color(str, syntax_type):
    if activate_colors:
        (c, attrs) = color_scheme[syntax_type]
        return colored(str, c, attrs=attrs)
    else:
        return str


def display(row):
    if row['kind'] in function_kinds:
        str = display_function(row)
    else:
        kind = display_entity_kind(row)
        type = get_entity_name(get_entity_type(row['id']))
        str = "{} {} : {}".format(kind, row['name'], color(type, 'type'))
              # print(list(row))

    print(str)
    print("\tin " + display_location(row))

def display_location(row):
    q = "SELECT path FROM files WHERE id ={}".format(row['decl_file'])
    en = conn.execute(q).fetchone()
    path = en['path'] if en else '?'
    return "{}:{}:{}".format(path, row['decl_line'], row['decl_column'])

def display_function(row):
    kind = display_entity_kind(row)
    package = display_package(row)
    signature = display_signature(row)
    return ("{} {}.{} : {}".format(kind, package, row['name'], signature))

e_kinds = {}
def display_entity_kind(row):
    global e_kinds
    if not e_kinds:
        q = "SELECT * FROM entity_kinds"
        e_kinds = dict([(row['id'],row['display']) for row in conn.execute(q)])
    kind = e_kinds[row['kind']]
    return color(kind, 'entity_kind')

def display_package(row):
    parents = []
    # 1. get decl_caller
    parent = row['decl_caller']
    # 2. get e2e (parent package)
    while parent != -1:
        parents.append(parent)
        q = ("SELECT toEntity FROM e2e WHERE fromEntity = {} AND kind = {} GROUP BY toEntity"
             .format(parent, 18))
        # print(q)
        res = conn.execute(q)
        parent_row = res.fetchone()
        if parent_row is None:
            break
        # print(list(parent_row)[0]['toEntity'])
        parent = parent_row['toEntity']

    parents.reverse()
    # print(list(map(get_entity_name, parents)))
    return '.'.join(map(get_entity_name, parents))

def get_entity_name(id):
    q = "SELECT name FROM entities WHERE id = {}".format(id)
    # print(q)
    en = conn.execute(q).fetchone()
    return en['name'] if en else '?'

def get_entity_type(id):
    # TODO: not very well optimized
    q = "SELECT toEntity as id FROM e2e LEFT JOIN entities ON (id = fromEntity) WHERE id = {} AND e2e.kind = {}".format(id, 11)
    # print(q)
    en = conn.execute(q).fetchone()
    return en['id'] if en else '-1'

def display_signature(row):
    pq = ("SELECT e2e.kind as kind, e2e.toEntity as id, e_param.name AS name, e_type.name AS type FROM e2e "
          " LEFT JOIN entities AS e_param ON (e2e.toEntity = e_param.id)" # get name
          " LEFT JOIN e2e AS e2e_type ON (e2e_type.fromEntity = e_param.id AND e2e_type.kind = 11)" # get type entity
          " LEFT JOIN entities as e_type ON (e2e_type.toEntity = e_type.id)" # get type name
          " WHERE e2e.fromEntity = {} AND e2e.kind in (12,13,14,15)"
          " GROUP BY e2e_type.fromEntity").format(row['id']) # get type name

    kind_map = {
        12 : 'in',
        13 : 'out',
        14 : 'in out',
        15 : 'access'
    }
    params = ["({}) {} : {}".format(color(kind_map[r['kind']], 'param_kind'), r['name'], color(r['type'], 'type'))
              for r in conn.execute(pq)]

    tq = ("SELECT kind, toEntity as id FROM e2e WHERE fromEntity = {} AND kind = 11 GROUP BY fromEntity, kind, toEntity ORDER BY order_by"
          .format(row['id']))
    r = conn.execute(tq).fetchone()
    if r:
        params.append("({}) {}".format(color('ret', 'param_kind'),
                                      color(get_entity_name(r['id']), 'type')))

    return ' -> '.join(params) if params else '()'

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: {0} gnatinspect.db query".format(sys.argv[0]))
        print("Supported queries: ")
        print("   'abs': find any entity with the name 'abs'")
        print("   'max : Share -> Share': find functions or procedure with the"
              "          name 'max' with two parameters of type 'Share'")
        print("   'def : Blah': find any entity with the name 'max' of type 'Share'")
        print("   '(x,y,z) def': find any entity with the name 'def' and kinds x, y or z")

        for k,v in entity_kinds.items():
            print("{} : {}".format(k,v))

        # cols = 3
        # elen = len(entity_kinds)
        # per_col = [[], [], []]
        # i = 0
        # for k,v in range(elen):
        #     per_col[j % cols] = "{} : {}".format(k,v)
        #     i += 1
        # for i in range(cols);


        sys.exit(1)

    db_path = sys.argv[1]
    query_string = sys.argv[2]
    # try:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    query = query_builder(query_string)
    for row in conn.execute(query):
        display(row)

    conn.close()
    # except Exception e:
    #     print("Could not connect to database {}, {}".format(db_path, e))
        # sys.exit(1)
