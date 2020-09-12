_ENV = None

def read():
  global _ENV
  if _ENV is not None:
    return _ENV

  with open('../.env', 'r') as f:
    contents = f.readlines()

  _ENV = {}
  for content in contents:
    content = content.strip()
    if len(content) == 0 or content.startswith('#'): continue

    [key, val] = content.split('=', 1)
    _ENV[key] = val
  return _ENV
