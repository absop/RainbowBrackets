import sublime


class Loger:
    debug = False

    def print(*args):
        if Loger.debug:
            print("RainbowBrackets:", *args)

    def warn(*args):
        print("RainbowBrackets:", *args)

    def error(errmsg):
        sublime.error_message("RainbowBrackets: " + errmsg)
