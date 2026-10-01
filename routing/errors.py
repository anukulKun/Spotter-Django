class ApiError(Exception):
    def __init__(self, code, message, status, details=None):
        self.code = code
        self.message = message
        self.status = status
        self.details = details or {}
