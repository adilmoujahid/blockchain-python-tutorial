import re
from uuid import uuid4
from typing import final

MAX_REPUTATION: final = 5
MYSELF_STRING: final = "myself"
URL_REGEX: final = r'(?i)\b((?:[a-z][\w-]+:(?:/{1,3}|[a-z0-9%])|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:\'".,<>?«»“”‘’]))'


class Node(object):
    def __init__(self, url: str, reputation: float = 1, address: str = str(uuid4()).replace('-', '')):
        if not 0 <= reputation <= MAX_REPUTATION:
            raise ValueError("Reputation must between 0 and " + str(MAX_REPUTATION) + "!")
        if not (re.match(URL_REGEX, url) or url.lower() == MYSELF_STRING.lower()):
            raise ValueError("Node url must be a valid IPv4 or IPv6 address!")
        self.__reputation = reputation
        self.__url = url
        self.__address = address

    @property
    def url(self) -> str:
        return self.__url

    @url.setter
    def url(self, url: str):
        if not (re.match(URL_REGEX, url) or url.lower() == MYSELF_STRING.lower()):
            raise ValueError("Node url must be a valid IPv4 or IPv6 address!")
        self.__url = url

    @url.deleter
    def url(self):
        raise AttributeError("The 'node_url' attribute cannot be deleted!")

    @property
    def reputation(self) -> float:
        return self.__reputation

    @reputation.setter
    def reputation(self, reputation: float):
        if not 0 <= reputation <= MAX_REPUTATION:
            raise ValueError("Reputation must between 0 and " + str(MAX_REPUTATION) + "!")
        self.__url = reputation

    @reputation.deleter
    def reputation(self):
        raise AttributeError("The 'reputation' attribute cannot be deleted!")

    @property
    def address(self) -> str:
        return self.__address

    @address.setter
    def address(self, address: str):
        self.__address = address

    @address.deleter
    def address(self):
        raise AttributeError("The 'address' attribute cannot be deleted!")
