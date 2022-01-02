import json
import sublime


class Debuger():
    debug = False
    employer = "RainbowBrackets"

    @classmethod
    def print(cls, *args, **kwargs):
        if cls.debug:
            print(f"{cls.employer}:", *args, **kwargs)

    @classmethod
    def pprint(cls, obj):
        class setEncoder(json.JSONEncoder):
            def default(self, obj):
                if isinstance(obj, set):
                    return sorted(obj)
                return json.JSONEncoder.default(self, obj)

        if cls.debug:
            print(f"{cls.employer}:", json.dumps(obj,
                cls=setEncoder, indent=4,
                sort_keys=True, ensure_ascii=False))

