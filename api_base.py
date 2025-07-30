class APIBase:
    def send_request(self, **kwargs):
        raise NotImplementedError("Метод send_request должен быть реализован в подклассе")