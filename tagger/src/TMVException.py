class TMVException(Exception):
  ID_PARSE_JSON = 0
  ID_DB_CONNECTION = 1
  ID_TAGGED_NOT_FOUND = 2
  ID_FAULTY_INPUT = 3

  ID_404 = 404
  ID_405 = 405

  def __init__(self, id, msg=''):
    self.error_id = id
    self.error_msg = msg
