from contextlib import closing
from datetime import datetime
from functools import partial
import getpass
import inspect
import json
import locale
import re
import readline
import traceback
import urllib
import urllib2
import urlparse

class MtGoxError(Exception):
    pass

class NoCredentialsError(Exception):
    pass

class LoginError(Exception):
    pass

class MtGox(object):    
    def __init__(self):
        self.unset_credentials()
        self.__url_parts = urlparse.urlsplit("https://mtgox.com/code/")
        self.__headers = {
            "User-Agent": u"goxsh"
        }
    
    def get_username(self):
        return self.__credentials[0] if self.have_credentials() else None
    
    def have_credentials(self):
        return self.__credentials != None
        
    def set_credentials(self, username, password):
        if len(username) == 0:
            raise ValueError(u"Empty username.")
        if len(password) == 0:
            raise ValueError(u"Empty password.")
        self.__credentials = (username, password)

    def unset_credentials(self):
        self.__credentials = None
    
    def buy(self, amount, price):
        return self.__get_json("buyBTC.php", params = {
            u"amount": amount,
            u"price": price
        })
    
    def cancel_order(self, kind, oid):
        return self.__get_json("cancelOrder.php", params = {
            u"oid": oid,
            u"type": kind
        })[u"orders"]
    
    def get_balance(self):
        return self.__get_json("getFunds.php")
    
    def get_orders(self):
        return self.__get_json("getOrders.php")[u"orders"]
    
    def get_ticker(self):
        return self.__get_json("data/ticker.php", auth = False)[u"ticker"]
    
    def sell(self, amount, price):
        return self.__get_json("sellBTC.php", params = {
            u"amount": amount,
            u"price": price
        })
    
    def withdraw(self, address, amount):
        return self.__get_json("withdraw.php", params = {
            u"group1": u"BTC",
            u"btca": address,
            u"amount": amount
        })    

    def __get_json(self, rel_path, params = {}, auth = True):
        if auth and not self.have_credentials():
            raise NoCredentialsError()
        params = params.items()
        if auth:
            params += [
                (u"name", self.__credentials[0]),
                (u"pass", self.__credentials[1])
            ]
        post_data = urllib.urlencode(params) if len(params) > 0 else None
        url = urlparse.urlunsplit((
            self.__url_parts.scheme,
            self.__url_parts.netloc,
            self.__url_parts.path + rel_path,
            self.__url_parts.query,
            self.__url_parts.fragment
        ))
        req = urllib2.Request(url, post_data, self.__headers)
        with closing(urllib2.urlopen(req, post_data)) as res:
            data = json.load(res)
        if u"error" in data:
            if data[u"error"] == u"Not logged in.":
                raise LoginError()
            else:
                raise MtGoxError(data[u"error"])
        else:
            return data

class CommandError(Exception):
    pass

class ArityError(Exception):
    pass

class GoxSh(object):
    def __init__(self, mtgox, encoding):
        self.__mtgox = mtgox
        self.__encoding = encoding
        readline.parse_and_bind("tab: complete")
        readline.set_completer(self.__complete)
    
    def prompt(self):
        proc = None
        args = []
        try:
            try:
                text = u"%s$ " % (self.__mtgox.get_username() or u"")
                line = raw_input(text).decode(self.__encoding).split()
                if line:
                    cmd, args = line[0], line[1:]
                    proc = self.__get_cmd_proc(cmd, self.__unknown(cmd))
            except EOFError, e:
                print "exit"
                proc = self.__cmd_exit__
            if proc != None:
                (min_arity, max_arity) = self.__get_proc_arity(proc)
                arg_count = len(args)
                if min_arity <= arg_count and (max_arity == None or arg_count <= max_arity):
                    proc(*args)
                else:
                    if min_arity == max_arity:
                        arity_text = unicode(min_arity)
                    elif max_arity == None:
                        arity_text = u"%s+" % min_arity
                    else:
                        arity_text = u"%s-%s" % (min_arity, max_arity)
                    arg_text = u"argument" + (u"" if arity_text == u"1" else u"s")
                    raise ArityError(u"Expected %s %s, got %s" % (arity_text, arg_text, arg_count))
        except MtGoxError, e:
            print u"Mt. Gox error: %s" % e
        except EOFError, e:
            raise e
        except CommandError, e:
            print e
        except ArityError, e:
            print e
        except NoCredentialsError:
            print u"No login credentials entered. Use the login command first."
        except LoginError:
            print u"Mt. Gox rejected the login credentials. Maybe you made a typo?"
        except KeyboardInterrupt:
            print
        except Exception, e:
            traceback.print_exc()
    
    def __get_cmd_proc(self, cmd, default = None):
        return getattr(self, "__cmd_%s__" % cmd, default)
    
    def __cmd_name(self, attr):
        match = re.match(r"^__cmd_(.+)__$", attr)
        return match.group(1) if match != None else None
    
    def __get_cmds(self, prefix = ""):
        return sorted(
            filter(
                lambda cmd: cmd != None and cmd.startswith(prefix),
                (self.__cmd_name(attr) for attr in dir(self))
            )
        )
    
    def __print_cmd_info(self, cmd):
        proc = self.__get_cmd_proc(cmd)
        if proc != None:
            print cmd,
            argspec = inspect.getargspec(proc)
            args = argspec.args[1:]
            if argspec.defaults != None:
                i = -1
                for default in reversed(argspec.defaults):
                    args[i] = (args[i], default)
                    i -= 1
            for arg in args:
                if not isinstance(arg, tuple):
                    print arg,
                elif arg[1]:
                    print "[%s=%s]" % arg,
                else:
                    print "[%s]" % arg[0],
            if argspec.varargs != None:
                print "[...]",
            print
            doc = proc.__doc__ or "--"
            for line in doc.splitlines():
                print "    " + line
        else:
            self.__unknown(cmd)
    
    def __get_proc_arity(self, proc):
        argspec = inspect.getargspec(proc)
        maximum = len(argspec.args[1:])
        minimum = maximum - (len(argspec.defaults) if argspec.defaults != None else 0)
        if argspec.varargs != None:
            maximum = None
        return (minimum, maximum)
    
    def __complete(self, text, state):
        cmds = self.__get_cmds(text)
        try:
            return self.__get_cmds(text)[state] + (" " if len(cmds) == 1 else "")
        except IndexError:
            return None
    
    def __print_balance(self, balance):
        print u"BTC:", balance[u"btcs"]
        print u"USD:", balance[u"usds"]
    
    def __print_order(self, order):
        kind = {1: u"sell", 2: u"buy"}[order[u"type"]]
        timestamp = datetime.fromtimestamp(int(order[u"date"])).strftime("%Y-%m-%d %H:%M:%S")
        properties = []
        if bool(int(order[u"dark"])):
            properties.append(u"dark")
        if order[u"status"] == u"2":
            properties.append(u"not enough funds")
        print "[%s] %s %s: %sBTC @ %sUSD%s" % (timestamp, kind, order[u"oid"], order[u"amount"], order[u"price"], (" (" + ", ".join(properties) + ")" if properties else ""))
        
    def __unknown(self, cmd):
        def __unknown_1(*args):
            print u"%s: Unknown command." % cmd
        return __unknown_1
    
    def __cmd_balance__(self):
        u"Display account balance."
        self.__print_balance(self.__mtgox.get_balance())
    
    def __cmd_buy__(self, amount, price):
        u"Buy bitcoins."
        buy_result = self.__mtgox.buy(amount, price)
        statuses = filter(None, buy_result[u"status"].split(u"<br>"))
        for status in statuses:
            print status
        for order in buy_result[u"orders"]:
            self.__print_order(order)
    
    def __cmd_cancel__(self, kind, order_id):
        u"Cancel the order with the specified kind (buy or sell) and order ID."
        try:
            num_kind = {u"sell": 1, u"buy": 2}[kind]
            orders = self.__mtgox.cancel_order(num_kind, order_id)
            print u"Canceled %s %s." % (kind, order_id)
            if orders:
                for order in orders:
                    self.__print_order(order)
            else:
                print u"No remaining orders."
        except KeyError:
            raise CommandError(u"%s: Invalid order kind." % kind)
    
    def __cmd_exit__(self):
        u"Exit goxsh."
        raise EOFError()
    
    def __cmd_help__(self, command = None):
        u"Show help for the specified command or list all commands if none is given."
        if command == None:
            cmds = self.__get_cmds()
        else:
            cmds = [command]
        for cmd in cmds:
            self.__print_cmd_info(cmd)
    
    def __cmd_login__(self, username = u""):
        u"Set login credentials."
        while len(username) == 0:
            username = raw_input("Username: ").decode(self.__encoding)
        readline.remove_history_item(readline.get_current_history_length() - 1)
        password = u""
        while len(password) == 0:
            password = getpass.getpass()
        self.__mtgox.set_credentials(username, password)
    
    def __cmd_logout__(self):
        u"Unset login credentials."
        self.__mtgox.unset_credentials()
    
    def __cmd_orders__(self, kind = None):
        u"List open orders.\nSpecifying a kind (buy or sell) will list only orders of that kind."
        try:
            num_kind = {None: None, u"sell": 1, u"buy": 2}[kind]
            orders = self.__mtgox.get_orders()
            if orders:
                for order in orders:
                    if num_kind in {None, order[u"type"]}:
                        self.__print_order(order)
            else:
                print "No orders."
        except KeyError:
            raise CommandError(u"%s: Invalid order kind." % kind)
                
    def __cmd_sell__(self, amount, price):
        u"Sell bitcoins."
        sell_result = self.__mtgox.sell(amount, price)
        statuses = filter(None, sell_result[u"status"].split(u"<br>"))
        for status in statuses:
            print status
        for order in sell_result[u"orders"]:
            self.__print_order(order)

    def __cmd_ticker__(self):
        u"Display ticker."
        ticker = self.__mtgox.get_ticker()
        print u"Last: %s" % ticker[u"last"]
        print u"Buy: %s" % ticker[u"buy"]
        print u"Sell: %s" % ticker[u"sell"]
        print u"Hight: %s" % ticker[u"high"]
        print u"Low: %s" % ticker[u"low"]
        print u"Volume: %s" % ticker[u"vol"]

    def __cmd_withdraw__(self, address, amount):
        u"Withdraw bitcoins."
        withdraw_info = self.__mtgox.withdraw(address, amount)
        print withdraw_info[u"status"]
        print "Updated balance:"
        self.__print_balance(withdraw_info)

def main():
    locale.setlocale(locale.LC_ALL, "")
    encoding = locale.getpreferredencoding()
    sh = GoxSh(MtGox(), encoding)
    print u"Welcome to goxsh!"
    try:
        while True:
            sh.prompt()
    except EOFError:
        pass

if __name__ == "__main__":
    main()
