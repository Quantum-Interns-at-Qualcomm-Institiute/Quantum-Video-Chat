def HandleExceptions(func: callable):
    """
    Decorator to handle commonly encountered
    exceptions at Socket Client endpoints.

    NOTE: This should never be called explicitly
    """

    def wrapper(self, *args, **kwargs):
        try:
            return func(self, *args, **kwargs)
        except Exception as e:
            self.logger.error(e)
            raise e
    wrapper.__name__ = func.__name__
    return wrapper
