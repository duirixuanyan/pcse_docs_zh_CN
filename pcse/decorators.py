# -*- coding: utf-8 -*-
# 版权所有 (c) 2004-2024 Wageningen Environmental Research, Wageningen-UR
# Allard de Wit (allard.dewit@wur.nl), 2024年3月
from functools import wraps


class descript(object):
    def __init__(self, f, lockattr):
        self.f = f
        self.lockattr = lockattr
    
    def __get__(self, instance, klass):
        if instance is None:
            # 请求了类方法
            return self.make_unbound(klass)
        return self.make_bound(instance)
    
    def make_unbound(self, klass):
        @wraps(self.f)
        def wrapper(*args, **kwargs):
            '''这个文档会消失 :)'''
            raise TypeError(
                'unbound method %s() must be called with %s instance '
                'as first argument (got nothing instead)'
                %
                (self.f.__name__, klass.__name__)
            )
        return wrapper
    
    def make_bound(self, instance):
        @wraps(self.f)
        def wrapper(*args, **kwargs):
            '''这个文档会消失 :)'''
            #print "调用被装饰的方法 %r ，属于 %r，带参数 %s "\
            #      %(self.f.__name__, instance, args)
            attr = getattr(instance, self.lockattr)
            if attr is not None:
                attr.unlock()
            ret = self.f(instance, *args, **kwargs)
            attr = getattr(instance, self.lockattr)
            if attr is not None:
                attr.lock()
            return ret
        # 这个实例以后不需要再查找描述符了，
        # 让它可以直接找到 wrapper ：
        setattr(instance, self.f.__name__, wrapper)
        return wrapper

def prepare_states(f):
    '''
    类方法装饰器，用于解锁和锁定 states 对象。

    它使用描述符来延迟方法包装器的定义。详情可见：
    http://wiki.python.org/moin/PythonDecoratorLibrary#Class_method_decorator_using_instance
    '''

    return descript(f, "states")

def prepare_rates(f):
    '''
    类方法装饰器，用于解锁和锁定 rates 对象。

    它使用描述符来延迟方法包装器的定义。详情可见：
    http://wiki.python.org/moin/PythonDecoratorLibrary#Class_method_decorator_using_instance
    '''

    return descript(f, "rates")

def main():
    class testclass(object):
        class strates(object):
            def lock(self):
                print("Locking!")
            def unlock(self):
                print("Unlocking!")
    
        def __init__(self):
            self.myattr = 10
            self.rates = self.strates()
            self.states = self.strates()
        
        @prepare_states
        def integrate(self, a, b, c):
            print("executing _integrate with parameters %s,%s,%s!" % (a, b, c))
        @prepare_rates
        def calc_rates(self, a, b, c):
            print("executing _calc_rates with parameters %s,%s,%s!" % (a, b, c))
            
            
    tc = testclass()
    
    tc.integrate(1, 2, 3)
    tc.calc_rates(4, 5, 6)

if __name__ == "__main__":
    main()