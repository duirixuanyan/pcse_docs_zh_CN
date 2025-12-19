# -*- coding: utf-8 -*-
# 版权所有 (c) 2004-2024 Wageningen Environmental Research, Wageningen-UR
# Allard de Wit (allard.dewit@wur.nl), 2024年3月
from __future__ import print_function
import datetime

from .base import dispatcher
from .base import AncillaryObject, VariableKiosk
from .traitlets import HasTraits, Instance, Bool, Int, Enum
from . import signals
from .util import is_a_dekad, is_a_month, is_a_week


class Timer(AncillaryObject):
    """该类为WOFOST作物模型实现了一个基本的定时器。
    
    该对象实现了一个简单的定时器，每次调用时以一天为固定时间步长递增当前时间并返回其数值。此外，
    它可以按日、旬或月的时间步长生成OUTPUT信号，这些信号可以被捕获以便存储模拟状态以备后用。
    
    初始化定时器::

        timer = Timer(start_date, kiosk, final_date, mconf)
        CurrentDate = timer()
        
    **发送或处理的信号:**
 
        * "OUTPUT": 当生成输出的条件为真时发送，
          这取决于输出类型和间隔。

  """

    start_date = Instance(datetime.date)
    end_date = Instance(datetime.date)
    current_date = Instance(datetime.date)
    time_step = Instance(datetime.timedelta)
    interval_type = Enum(["daily", "weekly", "dekadal", "monthly"])
    output_weekday = Int()
    interval_days = Int()
    generate_output = Bool(False)
    day_counter = Int(0)
    first_call = Bool(True)
    _in_crop_cycle = Bool()

    def initialize(self, kiosk, start_date, end_date, mconf):
        """
        :param day: 模拟的起始日期
        :param kiosk: PCSE实例的变量kiosk
        :param end_date: 模拟的结束日期。例如，该日期
            对于单一作季来说为(START_DATE + MAX_DURATION)。
            此日期不是收获日期，因为收获的信号由`AgroManagement`模块处理。
        :param mconf: ConfigurationLoader对象，定时器需要访问配置属性
            mconf.OUTPUT_INTERVAL, mconf.OUTPUT_VARS 和 mconf.OUTPUT_INTERVAL_DAYS

        """
        
        self.kiosk = kiosk
        self.start_date = start_date
        self.end_date = end_date
        self.current_date = start_date
        # self.day_counter = 0
        # 生成输出的相关设置。注意，如果没有列出OUTPUT_VARS，
        # 则不会生成任何OUTPUT信号。
        self.generate_output = bool(mconf.OUTPUT_VARS)
        self.interval_type = mconf.OUTPUT_INTERVAL.lower()
        self.output_weekday = mconf.OUTPUT_WEEKDAY
        self.interval_days = mconf.OUTPUT_INTERVAL_DAYS
        self.time_step = datetime.timedelta(days=1)
        # self.first_call = True

    def __call__(self):
        
        # 首次调用时只返回当前日期，不增加时间
        if self.first_call is True:
            self.first_call = False
            self.logger.debug("Model time at first call: %s" % self.current_date)
        else:
            self.current_date += self.time_step
            self.day_counter += 1
            self.logger.debug("Model time updated to: %s" % self.current_date)

        # 检查是否需要生成输出
        output = False
        if self.generate_output:
            if self.interval_type == "daily":
                if (self.day_counter % self.interval_days) == 0:
                    output = True
            elif self.interval_type == "weekly":
                if is_a_week(self.current_date, self.output_weekday):
                    output = True 
            elif self.interval_type == "dekadal":
                if is_a_dekad(self.current_date):
                    output = True
            elif self.interval_type == "monthly":
                if is_a_month(self.current_date):
                    output = True

        # 如果需要则发送输出信号
        if output:
            self._send_signal(signal=signals.output)
            
        # 如果已到达结束日期则发送终止信号
        if self.current_date >= self.end_date:
            msg = "Reached end of simulation period as specified by END_DATE."
            self.logger.info(msg)
            self._send_signal(signal=signals.terminate)
            
        return self.current_date, float(self.time_step.days)


def simple_test():
    "仅用于测试定时器过程"

    class Container(object):
        pass

    def on_OUTPUT():
        print("Output generated.")
    
    Start = datetime.date(2000, 1, 1)
    End = datetime.date(2000, 2, 1)
    kiosk = VariableKiosk()
    dispatcher.connect(on_OUTPUT, signal=signals.output,
                       sender=dispatcher.Any)

    mconf = Container()
    mconf.OUTPUT_INTERVAL = "dekadal"
    mconf.OUTPUT_INTERVAL_DAYS = 4
    mconf.OUTPUT_VARS = ["dummy"]

    print("-----------------------------------------")
    print("Dekadal output")
    print("-----------------------------------------")
    timer = Timer(Start, kiosk, End, mconf)
    for i in range(100):
        today = timer()

    print("-----------------------------------------")
    print("Monthly output")
    print("-----------------------------------------")
    mconf.OUTPUT_INTERVAL = "monthly"
    timer = Timer(Start, kiosk, End, mconf)
    for i in range(150):
        today = timer()

    print("-----------------------------------------")
    print("daily output with 4 day intervals")
    print("-----------------------------------------")
    mconf.OUTPUT_INTERVAL = "daily"
    timer = Timer(Start, kiosk, End, mconf)
    for i in range(150):
        today = timer()

if __name__ == '__main__':
    simple_test()
