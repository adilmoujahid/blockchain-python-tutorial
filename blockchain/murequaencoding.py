import json
import pickle
from typing import Any


class ObjectJSONEncoder(json.JSONEncoder):
    def default(self, o: Any) -> str:
        pickle_object = pickle.dumps(o, 0)
        pickle_object_string = pickle_object.decode()
        encoded_object = {"object": pickle_object_string}
        return json.dumps(encoded_object)


