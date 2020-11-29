import psycopg2
import dotenv
from TMVException import TMVException
from collections import Counter

def open_connection():
  try:
    env = dotenv.read()
    return psycopg2.connect(dbname=env['TMV_DB_NAME'], user=env['TMV_DB_USER'], password=env['TMV_DB_PASSWORD'], host=env['TMV_DB_NETWORK_ALIAS'], port=5432)
  except psycopg2.OperationalError as e:
    raise TMVException(TMVException.ID_DB_CONNECTION, 'Failed to connect to database')

def get_table_names():
  env = dotenv.read()
  schema = env['TMV_DB_SCHEMA_NAME']

  retval = {}
  retval['schema']              = schema
  retval['multitags']           = schema + '.' + env['TMV_DB_MULTITAGS_TABLE_NAME']
  retval['valuetags']           = schema + '.' + env['TMV_DB_VALUETAGS_TABLE_NAME']
  retval['tagged']              = schema + '.' + env['TMV_DB_TAGGED_TABLE_NAME']
  retval['tagged_multitags']    = schema + '.' + env['TMV_DB_TAGGED_MULTITAGS_BRIDGE_TABLE_NAME']
  retval['tagged_valuetags']    = schema + '.' + env['TMV_DB_TAGGED_VALUETAGS_BRIDGE_TABLE_NAME']

  retval['multitags_multitags'] = schema + '.' + env['TMV_DB_MULTITAGS_MULTITAGS_BRIDGE_TABLE_NAME']

  return retval

def is_valid_tag_name(name):
  if not isinstance(name, str):
    name = name['name']

  for value in ['%']:
    if value in name:
      return False

  if name.startswith(('-')):
    return False

  if query_is_value_query(name):
    return False

  return True

def check_if_tags_are_valid(tags, prefix):
  for tag in tags:
    if not is_valid_tag_name(tag):
      raise TMVException(TMVException.ID_INVALID_TAG_NAME, '{} tag \'{}\' is invalidly formatted'.format(prefix, tag))

def create_tables():
  conn = None
  cur = None

  try:
    conn = open_connection()
    cur = conn.cursor()

    names = get_table_names()
    cur.execute('CREATE SCHEMA IF NOT EXISTS {}'.format(names['schema']))
    cur.execute('CREATE TABLE IF NOT EXISTS {} (id bigserial PRIMARY KEY, value text UNIQUE NOT NULL)'.format(names['multitags']))
    cur.execute('CREATE TABLE IF NOT EXISTS {} (id bigserial PRIMARY KEY, name text NOT NULL, value bigint NOT NULL, UNIQUE(name, value))'.format(names['valuetags']))
    cur.execute('CREATE TABLE IF NOT EXISTS {} (id bigserial PRIMARY KEY, value text UNIQUE NOT NULL)'.format(names['tagged']))
    cur.execute('CREATE TABLE IF NOT EXISTS {} (tagged_id bigint NOT NULL REFERENCES {}(id), tag_id bigint NOT NULL REFERENCES {}(id), UNIQUE(tagged_id, tag_id))'.format(names['tagged_multitags'], names['tagged'], names['multitags']))
    cur.execute('CREATE TABLE IF NOT EXISTS {} (tagged_id bigint NOT NULL REFERENCES {}(id), tag_id bigint NOT NULL REFERENCES {}(id), UNIQUE(tagged_id, tag_id))'.format(names['tagged_valuetags'], names['tagged'], names['valuetags']))
    cur.execute('CREATE TABLE IF NOT EXISTS {} (first_tag_id bigint NOT NULL REFERENCES {}(id), second_tag_id bigint NOT NULL REFERENCES {}(id), UNIQUE(first_tag_id, second_tag_id))'.format(names['multitags_multitags'], names['multitags'], names['multitags']))
    conn.commit()
  finally:
    if cur:
      cur.close()
    if conn:
      conn.close()

def query_is_value_query(query):
  if not query.endswith('}'):
    return False

  start_index = query.rfind('{')
  if start_index == -1:
    return False

  val = query[start_index + 1:-1].strip()
  if val.startswith(('>=', '<=', '!=', '<>')):
    val = val[2:].strip()
  elif val.startswith(('>', '<')):
    val = val[1:].strip()
  else:
    return False

  if val.startswith('-'):
    val = val[1:]
  return val.isdigit()

def split_query(query):
  retval = {
    'positive': [],
    'negative': [],
    'pos_value': [],
    'neg_value': []
  }

  for q in query:
    if q.startswith('-'):
      q = q[1:]
      if query_is_value_query(q):
        retval['neg_value'].append(q)
      else:
        retval['negative'].append(q)
    elif query_is_value_query(q):
      retval['pos_value'].append(q)
    else:
      retval['positive'].append(q)

  return retval

def get_query_ids(value, cur, names, forbidden_ids):
  forbidden_ids_string = '(' + ','.join(str(i) for i in forbidden_ids) + ')'
  comparator = 'LIKE' if '%' in value else '='

  cur.execute("""
SELECT DISTINCT t.id FROM """ + names['tagged'] + """ AS t WHERE """ + ('NOT t.id IN {} AND '.format(forbidden_ids_string) if len(forbidden_ids) > 0 else '') + """t.id IN (
  SELECT DISTINCT t.id FROM """ + names['tagged'] + """ AS t
    JOIN """ + names['tagged_multitags'] + """ AS mtt ON mtt.tagged_id = t.id
    JOIN """ + names['multitags'] + """ AS mt ON mtt.tag_id = mt.id
    WHERE mt.value """ + comparator + """ %s
) OR t.id IN (
  SELECT DISTINCT t.id FROM """ + names['tagged'] + """ AS t
    JOIN """ + names['tagged_valuetags'] + """ AS vtt ON vtt.tagged_id = t.id
    JOIN """ + names['valuetags'] + """ AS vt ON vtt.tag_id = vt.id
    WHERE CONCAT(vt.name, CAST(vt.value AS text)) """ + comparator + """ %s
)""", (value, value))

  retval = []
  row = cur.fetchone()
  while row:
    retval.append(row[0])
    row = cur.fetchone()

  return retval

def get_value_query_ids(value, cur, names, forbidden_ids):
  forbidden_ids_string = '(' + ','.join(str(i) for i in forbidden_ids) + ')'
  [name, value] = value.split('{')
  comparator = value[0]
  value = value[1:-1]
  if not value[0].isnumeric():
    comparator += value[0]
    value = value[1:]
  value = int(value)

  cur.execute("""
SELECT DISTINCT t.id FROM """ + names['tagged'] + """ AS t""" + (' WHERE NOT t.id IN {}'.format(forbidden_ids_string) if len(forbidden_ids) > 0 else '') + """
  JOIN """ + names['tagged_valuetags'] + """ AS vtt ON vtt.tagged_id = t.id
  JOIN """ + names['valuetags'] + """ AS vt ON vtt.tag_id = vt.id
  WHERE vt.name = %s AND vt.value """ + comparator + """ %s
""", (name, value))

  retval = []
  row = cur.fetchone()
  while row:
    retval.append(row[0])
    row = cur.fetchone()
  return retval

# abc -def ghi:% jkl{>10} -mno{<=5}
# ============ LEADS TO ====================
# A = SELECT DISTINCT t.id FROM tmv.tagged AS t WHERE t.id IN (
#   SELECT DISTINCT t.id FROM tmv.tagged AS t
#     JOIN tmv.tagged_tags AS mtt ON mtt.tagged_id = t.id
#     JOIN tmv.tags AS mt ON mtt.tag_id = mt.id
#     WHERE mt.value = 'abc'
# ) OR t.id IN (
#   SELECT DISTINCT t.id FROM tmv.tagged AS t
#     JOIN tmv.tagged_valuetags AS vtt ON vtt.tagged_id = t.id
#     JOIN tmv.valuetags AS vt ON vtt.tag_id = vt.id
#     WHERE CONCAT(vt.name, CAST(vt.value AS text)) = 'abc'
# )
#
# B = SELECT DISTINCT t.id FROM tmv.tagged AS t WHERE t.id IN (
#   SELECT DISTINCT t.id FROM tmv.tagged AS t
#     JOIN tmv.tagged_tags AS mtt ON mtt.tagged_id = t.id
#     JOIN tmv.tags AS mt ON mtt.tag_id = mt.id
#     WHERE mt.value = 'def'
# ) OR t.id IN (
#   SELECT DISTINCT t.id FROM tmv.tagged AS t
#     JOIN tmv.tagged_valuetags AS vtt ON vtt.tagged_id = t.id
#     JOIN tmv.valuetags AS vt ON vtt.tag_id = vt.id
#     WHERE CONCAT(vt.name, CAST(vt.value AS text)) = 'def'
# )
#
# C = SELECT DISTINCT t.id FROM tmv.tagged AS t WHERE t.id IN (
#   SELECT DISTINCT t.id FROM tmv.tagged AS t
#     JOIN tmv.tagged_tags AS mtt ON mtt.tagged_id = t.id
#     JOIN tmv.tags AS mt ON mtt.tag_id = mt.id
#     WHERE mt.value LIKE 'ghi:%'
# ) OR t.id IN (
#   SELECT DISTINCT t.id FROM tmv.tagged AS t
#     JOIN tmv.tagged_valuetags AS vtt ON vtt.tagged_id = t.id
#     JOIN tmv.valuetags AS vt ON vtt.tag_id = vt.id
#     WHERE CONCAT(vt.name, CAST(vt.value AS text)) LIKE 'ghi:%'
# )
#
# D = SELECT DISTINCT t.id FROM tmv.tagged AS t
#   JOIN tmv.tagged_valuetags AS vtt ON vtt.tagged_id = t.id
#   JOIN tmv.valuetags AS vt ON vtt.tag_id = vt.id
#   WHERE vt.name = 'jkl' AND vt.value > 10
#
# E = SELECT DISTINCT t.id FROM tmv.tagged AS t
#   JOIN tmv.tagged_valuetags AS vtt ON vtt.tagged_id = t.id
#   JOIN tmv.valuetags AS vt ON vtt.tag_id = vt.id
#   WHERE vt.name = 'mno' AND vt.value <= 10
#
# Return list of distinct IDs that are in A & C & D, but also not in B or E
def search(query):
  conn = None
  cur = None
  query = split_query(query)

  try:
    conn = open_connection()
    cur = conn.cursor()
    names = get_table_names()

    neg_ids = []
    for q in query['negative']:
      neg_ids = neg_ids + get_query_ids(q, cur, names, neg_ids)
    for q in query['neg_value']:
      neg_ids = neg_ids + get_value_query_ids(q, cur, names, neg_ids)

    ids = []
    for q in query['positive']:
      ids = ids + get_query_ids(q, cur, names, neg_ids)
    for q in query['pos_value']:
      ids = ids + get_value_query_ids(q, cur, names, neg_ids)

    # Only keep IDs that were in all positive lists
    pos_amount = len(query['positive']) + len(query['pos_value'])
    id_counts = Counter(ids)
    ids = [id for id in ids if id_counts[id] == pos_amount]

    if len(ids) == 0:
      return []

    ids_string = '(' + ','.join(str(i) for i in ids) + ')'
    cur.execute('SELECT t.value FROM ' + names['tagged'] + ' AS t WHERE t.id IN {}'.format(ids_string))

    retval = []
    row = cur.fetchone()
    while row:
      retval.append(row[0])
      row = cur.fetchone()

    return retval
  finally:
    if cur:
      cur.close()
    if conn:
      conn.close()

def get(tagged, value_tags, multi_tags):
  conn = None
  cur = None

  try:
    conn = open_connection()
    cur = conn.cursor()
    names = get_table_names()

    tagged_ids = []
    for t in tagged:
      cur.execute('SELECT id FROM ' + names['tagged'] + ' WHERE value = %s', (t,))
      tagged_id = cur.fetchone()
      if tagged_id:
        tagged_ids.append([tagged_id[0], t])
      else:
        tagged_ids.append([None, t])

    retval = {}
    for tagged_id in tagged_ids:
      name = tagged_id[1]
      id = tagged_id[0]
      retval[name] = {}

      if id is None:
        if value_tags:
          retval[name]['value'] = []
        if multi_tags:
          retval[name]['multi'] = []
        continue

      if value_tags:
        # SELECT v.name, v.value FROM tmv.valuetags AS v, tmv.tagged_valuetags AS tv WHERE tv.tag_id = v.id AND tv.tagged_id = {tagged_id}
        cur.execute('SELECT v.name, v.value FROM ' + names['valuetags'] + ' AS v, ' + names['tagged_valuetags'] + ' AS tv WHERE tv.tag_id = v.id AND tv.tagged_id = %s', (id,))
        retval[name]['value'] = []
        row = cur.fetchone()
        while row:
          retval[name]['value'].append({'name': row[0], 'value': row[1]})
          row = cur.fetchone()

      if multi_tags:
        # SELECT v.name, v.value FROM tmv.tags AS v, tmv.tagged_tags AS tv WHERE tv.tag_id = v.id AND tv.tagged_id = {tagged_id}
        cur.execute('SELECT v.value FROM ' + names['multitags'] + ' AS v, ' + names['tagged_multitags'] + ' AS tv WHERE tv.tag_id = v.id AND tv.tagged_id = %s', (id,))
        retval[name]['multi'] = []
        row = cur.fetchone()
        while row:
          retval[name]['multi'].append(row[0])
          row = cur.fetchone()

    return retval
  finally:
    if cur:
      cur.close()
    if conn:
      conn.close()

def _get_implied_tags_for_multitag(multitag_id, cur, names, tags):
  implied_tags = []
  cur.execute('SELECT second_tag_id FROM ' + names['multitags_multitags'] + ' WHERE first_tag_id = %s', (multitag_id,))
  response = cur.fetchone()
  while response:
    if not response[0] in tags:
      implied_tags.append(response[0])
    response = cur.fetchone()

  # Only loop over tags not found previously
  for implied_tag in implied_tags:
    tags = _get_implied_tags_for_multitag(implied_tag, cur, names, tags + implied_tags)
  return list(set(tags + implied_tags))

def tag(tagged, value_tags, multi_tags):
  conn = None
  cur = None

  check_if_tags_are_valid(value_tags, 'Value')
  check_if_tags_are_valid(multi_tags, 'Multi')

  try:
    conn = open_connection()
    cur = conn.cursor()
    names = get_table_names()

    # Tagged
    cur.execute('INSERT INTO ' + names['tagged'] + ' (value) VALUES (%s) ON CONFLICT DO NOTHING RETURNING id', (tagged,))

    tagged_id = cur.fetchone()
    if tagged_id is None:
      cur.execute('SELECT id FROM ' + names['tagged'] + ' WHERE value = %s', (tagged,))
      tagged_id = cur.fetchone()
    tagged_id = tagged_id[0]

    # Value tags
    for tag in value_tags:
      cur.execute('INSERT INTO ' + names['valuetags'] + ' (name, value) VALUES (%s, %s) ON CONFLICT DO NOTHING RETURNING id', (tag['name'], tag['value']))

      tag_id = cur.fetchone()
      if tag_id is None:
        cur.execute('SELECT id FROM ' + names['valuetags'] + ' WHERE value = %s', (tag,))
        tag_id = cur.fetchone()
      tag_id = tag_id[0]

      cur.execute('INSERT INTO ' + names['tagged_valuetags'] + ' (tagged_id, tag_id) VALUES (%s, %s) ON CONFLICT DO NOTHING', (tagged_id, tag_id))

    # Multi tags
    for tag in multi_tags:
      cur.execute('INSERT INTO ' + names['multitags'] + ' (value) VALUES (%s) ON CONFLICT DO NOTHING RETURNING id', (tag,))

      tag_id = cur.fetchone()
      if tag_id is None:
        cur.execute('SELECT id FROM ' + names['multitags'] + ' WHERE value = %s', (tag,))
        tag_id = cur.fetchone()
      tag_id = tag_id[0]

      tag_ids = _get_implied_tags_for_multitag(tag_id, cur, names, [tag_id])
      for tag_id in tag_ids:
        cur.execute('INSERT INTO ' + names['tagged_multitags'] + ' (tagged_id, tag_id) VALUES (%s, %s) ON CONFLICT DO NOTHING', (tagged_id, tag_id))

    conn.commit()
  finally:
    if cur:
      cur.close()
    if conn:
      conn.close()

def _remove_tagged_if_no_tags(tagged_id, cur, names):
  cur.execute('SELECT COUNT(*) FROM ' + names['tagged_valuetags'] + ' WHERE tagged_id = %s', (tagged_id,))
  value_count = cur.fetchone()[0]
  cur.execute('SELECT COUNT(*) FROM ' + names['tagged_multitags'] + ' WHERE tagged_id = %s', (tagged_id,))
  multi_count = cur.fetchone()[0]
  if value_count == 0 and multi_count == 0:
    cur.execute('DELETE FROM ' + names['tagged'] + ' WHERE id = %s', (tagged_id,))

def _remove_multitag_if_unused(multitag_id, cur, names):
  cur.execute('SELECT COUNT(*) FROM ' + names['tagged_multitags'] + ' WHERE tag_id = %s', (multitag_id,))
  tagged_count = cur.fetchone()[0]
  cur.execute('SELECT COUNT(*) FROM ' + names['multitags_multitags'] + ' WHERE first_tag_id = %s OR second_tag_id = %s', (multitag_id, multitag_id))
  multi_multi_count = cur.fetchone()[0]
  if tagged_count == 0 and multi_multi_count == 0:
    cur.execute('DELETE FROM ' + names['multitags'] + ' WHERE id = %s', (multitag_id,))

def _remove_valuetag_if_unused(valuetag_id, cur, names):
  cur.execute('SELECT COUNT(*) FROM ' + names['tagged_valuetags'] + ' WHERE tag_id = %s', (valuetag_id,))
  tagged_count = cur.fetchone()[0]
  if tagged_count == 0:
    cur.execute('DELETE FROM ' + names['valuetags'] + ' WHERE id = %s', (valuetag_id,))

def untag(tagged, value_tags, multi_tags):
  conn = None
  cur = None

  try:
    conn = open_connection()
    cur = conn.cursor()
    names = get_table_names()

    cur.execute('SELECT id FROM ' + names['tagged'] + ' WHERE value = %s', (tagged,))
    tagged_id = cur.fetchone()
    if tagged_id is None:
      raise TMVException(TMVException.ID_TAGGED_NOT_FOUND, 'The given value \'{}\' could not be found in the database'.format(tagged))
    tagged_id = tagged_id[0]

    # Value tags
    for tag in value_tags:
      cur.execute('SELECT id FROM ' + names['valuetags'] + ' WHERE name = %s AND value = %s', (tag['name'], tag['value']))
      tag_id = cur.fetchone()
      if tag_id is None:
        continue # Tag could not be found
      tag_id = tag_id[0]
      cur.execute('DELETE FROM ' + names['tagged_valuetags'] + ' WHERE tagged_id = %s AND tag_id = %s', (tagged_id, tag_id))
      _remove_valuetag_if_unused(tag_id, cur, names)

    # Multi tags
    for tag in multi_tags:
      cur.execute('SELECT id FROM ' + names['multitags'] + ' WHERE value = %s', (tag,))
      tag_id = cur.fetchone()
      if tag_id is None:
        continue # Tag could not be found
      tag_id = tag_id[0]
      cur.execute('DELETE FROM ' + names['tagged_multitags'] + ' WHERE tagged_id = %s AND tag_id = %s', (tagged_id, tag_id))
      _remove_multitag_if_unused(tag_id, cur, names)

    # Tagged
    _remove_tagged_if_no_tags(tagged_id, cur, names)
    conn.commit()
  finally:
    if cur:
      cur.close()
    if conn:
      conn.close()

def untag_all(tagged):
  conn = None
  cur = None

  try:
    conn = open_connection()
    cur = conn.cursor()
    names = get_table_names()

    cur.execute('SELECT id FROM ' + names['tagged'] + ' WHERE value = %s', (tagged,))
    tagged_id = cur.fetchone()
    if tagged_id is None:
      raise TMVException(TMVException.ID_TAGGED_NOT_FOUND, 'The given value \'{}\' could not be found in the database'.format(tagged))
    tagged_id = tagged_id[0]

    # Value tags
    cur.execute('DELETE FROM ' + names['tagged_valuetags'] + ' WHERE tagged_id = %s RETURNING tag_id', (tagged_id,))
    value_tags = []
    tag_id = cur.fetchone()
    while tag_id:
      value_tags.append(tag_id[0])
      tag_id = cur.fetchone()

    for value_tag in value_tags:
      _remove_valuetag_if_unused(value_tag, cur, names)

    # Multitags
    cur.execute('DELETE FROM ' + names['tagged_multitags'] + ' WHERE tagged_id = %s RETURNING tag_id', (tagged_id,))
    multi_tags = []
    tag_id = cur.fetchone()
    while tag_id:
      multi_tags.append(tag_id[0])
      tag_id = cur.fetchone()

    for multi_tag in multi_tags:
      _remove_multitag_if_unused(multi_tag, cur, names)

    conn.commit()
  finally:
    if cur:
      cur.close()
    if conn:
      conn.close()

def rename(tagged, multitags, valuetags):
  conn = None
  cur = None

  try:
    conn = open_connection()
    cur = conn.cursor()
    names = get_table_names()

    for t in tagged:
      cur.execute('UPDATE ' + names['tagged'] + ' SET value = %s WHERE value = %s', (t['new'], t['old']))

    for t in multitags:
      cur.execute('UPDATE ' + names['multitags'] + ' SET value = %s WHERE value = %s', (t['new'], t['old']))

    for t in valuetags:
      cur.execute('UPDATE ' + names['valuetags'] + ' SET name = %s, value = %s WHERE name = %s AND value = %s', (t['new']['name'], t['new']['value'], t['old']['name'], t['old']['value']))

    conn.commit()
  finally:
    if cur:
      cur.close()
    if conn:
      conn.close()

def tag_tags(multitags):
  conn = None
  cur = None

  try:
    conn = open_connection()
    cur = conn.cursor()
    names = get_table_names()

    for parent_tag in multitags:
      cur.execute('SELECT id FROM ' + names['multitags'] + ' WHERE value = %s', (parent_tag,))
      parent_id = cur.fetchone()
      if not parent_id:
        continue # Tag couldn't be found
      parent_id = parent_id[0]

      for child_tag in multitags[parent_tag]:
        cur.execute('SELECT id FROM ' + names['multitags'] + ' WHERE value = %s', (child_tag,))
        child_id = cur.fetchone()
        if not child_id:
          cur.execute('INSERT INTO ' + names['multitags'] + ' (value) VALUES (%s) ON CONFLICT DO NOTHING RETURNING id', (child_tag,))
          child_id = cur.fetchone()
        child_id = child_id[0]
        if parent_id == child_id:
          continue # Can't tag self with self
        cur.execute('INSERT INTO ' + names['multitags_multitags'] + ' (first_tag_id, second_tag_id) VALUES (%s, %s) ON CONFLICT DO NOTHING', (parent_id, child_id))

    conn.commit()
  finally:
    if cur:
      cur.close()
    if conn:
      conn.close()

def get_tags(multi, value):
  conn = None
  cur = None

  try:
    conn = open_connection()
    cur = conn.cursor()
    names = get_table_names()
    retval = {}

    if multi:
      retval['multi_tags'] = []
      cur.execute('SELECT value FROM ' + names['multitags'])
      response = cur.fetchone()
      while response:
        retval['multi_tags'].append(response[0])
        response = cur.fetchone()

    if value:
      retval['value_tags'] = []
      cur.execute('SELECT name, value FROM ' + names['valuetags'])
      response = cur.fetchone()
      while response:
        retval['value_tags'].append({'name': response[0], 'value': response[1]})
        response = cur.fetchone()

    return retval
  finally:
    if cur:
      cur.close()
    if conn:
      conn.close()

def get_implied_tags(multitags):
  conn = None
  cur = None

  try:
    conn = open_connection()
    cur = conn.cursor()
    names = get_table_names()

    retval = {'multi_tags': {}}
    for multitag in multitags:
      retval['multi_tags'][multitag] = []
      cur.execute('SELECT id FROM ' + names['multitags'] + ' WHERE value = %s', (multitag,))
      multi_id = cur.fetchone()
      if not multi_id:
        continue
      multi_id = multi_id[0]

      cur.execute('SELECT value FROM ' + names['multitags'] + ' WHERE id IN (SELECT second_tag_id FROM ' + names['multitags_multitags'] + ' WHERE first_tag_id = %s)', (multi_id,))
      result = cur.fetchone()
      while result:
        retval['multi_tags'][multitag].append(result[0])
        result = cur.fetchone()
    return retval
  finally:
    if cur:
      cur.close()
    if conn:
      conn.close()

def untag_tags(multitags):
  conn = None
  cur = None

  try:
    conn = open_connection()
    cur = conn.cursor()
    names = get_table_names()

    for parent_tag in multitags:
      cur.execute('SELECT id FROM ' + names['multitags'] + ' WHERE value = %s', (parent_tag,))
      parent_id = cur.fetchone()
      if not parent_id:
        continue
      parent_id = parent_id[0]

      if multitags[parent_tag] == 'all':
        cur.execute('SELECT second_tag_id FROM ' + names['multitags_multitags'] + ' WHERE first_tag_id = %s', (parent_id,))
        child_ids = []
        response = cur.fetchone()
        while response:
          child_ids.append(response[0])
          response = cur.fetchone()
        cur.execute('DELETE FROM ' + names['multitags_multitags'] + ' WHERE first_tag_id = %s', (parent_id,))
        for child_id in child_ids:
          _remove_multitag_if_unused(child_id, cur, names)
      else:
        for child_tag in multitags[parent_tag]:
          cur.execute('SELECT id FROM ' + names['multitags'] + ' WHERE value = %s', (child_tag,))
          child_id = cur.fetchone()
          if not child_id:
            continue
          child_id = child_id[0]
          cur.execute('DELETE FROM ' + names['multitags_multitags'] + ' WHERE first_tag_id = %s AND second_tag_id = %s', (parent_id, child_id))
          _remove_multitag_if_unused(child_id, cur, names)

      _remove_multitag_if_unused(parent_id, cur, names)
    conn.commit()
  finally:
    if cur:
      cur.close()
    if conn:
      conn.close()

def delete_tags(multi, value):
  conn = None
  cur = None

  try:
    conn = open_connection()
    cur = conn.cursor()
    names = get_table_names()

    # Multitags
    for tag in multi:
      cur.execute('SELECT id FROM ' + names['multitags'] + ' WHERE value = %s', (tag,))
      multi_id = cur.fetchone()
      if not multi_id:
        continue
      multi_id = multi_id[0]
      cur.execute('DELETE FROM ' + names['multitags_multitags'] + ' WHERE first_tag_id = %s OR second_tag_id = %s', (multi_id, multi_id))
      cur.execute('DELETE FROM ' + names['tagged_multitags'] + ' WHERE tag_id = %s', (multi_id,))
      cur.execute('DELETE FROM ' + names['multitags'] + ' WHERE id = %s', (multi_id,))

    # Valuetags
    for tag in value:
      cur.execute('SELECT id FROM ' + names['valuetags'] + ' WHERE name = %s AND value = %s', (tag['name'], tag['value']))
      value_id = cur.fetchone()
      if not value_id:
        continue
      value_id = value_id[0]
      cur.execute('DELETE FROM ' + names['tagged_valuetags'] + ' WHERE id = %s', (value_id,))
      cur.execute('DELETE FROM ' + names['valuetags'] + ' WHERE id = %s', (value_id,))

    conn.commit()
  finally:
    if cur:
      cur.close()
    if conn:
      conn.close()
