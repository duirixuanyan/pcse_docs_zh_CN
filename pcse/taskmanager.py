# -*- coding: utf-8 -*-
# 版权所有 (c) 2004-2024 Wageningen Environmental Research, Wageningen-UR
# Allard de Wit (allard.dewit@wur.nl), 2024年3月
"""任务管理器，从数据库表中读取任务，并在任务完成时更新状态

定义的类:
 TaskManager
"""

import os
import logging
import sqlalchemy as sa
from sqlalchemy import select, and_, MetaData, Table
import socket

class TaskManager:
    """定义了一个任务管理器类，它从名为 'tasklist' 的表中读取任务。

    用法: tm = TaskManager(engine, dbtype=dbtype, tasklist)

    公共方法:
    get_task() - 从列表中选择一个“Pending”状态的任务
    set_task_finished(task) - 将任务状态设置为“Finished”
    set_task_error(task) - 将任务状态设置为“Error occurred”

    可以通过如下SQL命令（以MySQL为例）创建一个任务表::

        CREATE TABLE `tasklist` (
           `task_id` int(11) NOT NULL AUTO_INCREMENT,
           `status` char(16) DEFAULT NULL,
           `hostname` char(50) DEFAULT NULL,
           `process_id` int(11) DEFAULT NULL,
           `comment` varchar(200) DEFAULT NULL,
           `parameter1` int(11) DEFAULT NULL,
           `parameter2` decimal(10,2) DEFAULT NULL,

           ... 此处可添加更多列。

           PRIMARY KEY (`task_id`),
           KEY `status_ix` (`status`)
         );

    """
    validstatus = ['Pending', 'In progress', 'Finished',
                   'Error occurred']
    knowndatabases = ['mysql', 'oracle', 'sqlite']

#-------------------------------------------------------------------------------
    def __init__(self, engine, dbtype=None, tasklist='tasklist'):
        """TaskManager 的类构造函数。
        
        参数:
        * engine - SQLAlchemy 的 engine 对象

        关键字参数:
        * dbtype - 要连接的数据库类型，为'MySQL'，'ORACLE'或'SQLite'
        * tasklist - 要读取任务的表名，默认为 'tasklist'
        """
        db_ok = False
        if isinstance(dbtype, str):
            if dbtype.lower() in self.knowndatabases:
                db_ok = True
        if db_ok is False:
            msg = "keyword 'dbtype' should be one of %s" % self.knowndatabases
            raise RuntimeError(msg)
        if not isinstance(engine, sa.engine.base.Engine):
            msg = "Argument 'engine' should be SQLalchemy database engine, " \
                  "got %s" % engine
            raise RuntimeError(msg)

        self.dbtype = dbtype.lower()
        self.engine = engine
        self.logger = logging.getLogger("TaskManager")
        self.hostname = socket.gethostname()
        self.process_id = os.getpid()
        self.tasklist_tablename = tasklist

        # 检查任务表是否存在并且数据库可读
        try:
            conn = self.engine.connect()
            metadata = MetaData(conn)
            self.table_tasklist = Table(tasklist, metadata, autoload=True)
        except Exception as e:
            msg = "Unable to connect or tasklist table doesn't exist!"
            self.logger.exception(msg)
            raise RuntimeError(msg)

#-------------------------------------------------------------------------------
    def get_task(self):
        """返回一个状态为'Pending'的任务，交由处理单元。"""
        
        conn = self.engine.connect()
        self._lock_table(conn)
        tasklist = self.table_tasklist
        s = select([tasklist], and_(tasklist.c.status=='Pending'), 
                   order_by=[tasklist.c.task_id],
                   limit=1)
        r = conn.execute(s)
        row = r.fetchone()
        r.close()
        if row is None:
            self._unlock_table(conn)
            return None
        else:
            task = dict(row)
            u = tasklist.update(tasklist.c.task_id==task["task_id"])
            conn.execute(u, status='In progress',  hostname=self.hostname,
                         process_id=self.process_id)
        self._unlock_table(conn)
        return task
    
#-------------------------------------------------------------------------------
    def _lock_table(self, connection):
        """锁定TASKLIST表。注意，锁表/解锁通过直接发送SQL到数据库实现，而不是通过SQLAlchemy，
        因为SQLAlchemy不支持这种表级锁定。"""
    
        if self.dbtype=="mysql":
            connection.execute("LOCK TABLE %s WRITE" % self.tasklist_tablename)
        elif self.dbtype=="oracle":
            connection.execute("LOCK TABLE %s IN EXCLUSIVE MODE" %
                               self.tasklist_tablename)
        elif self.dbtype=="sqlite":
            pass # SQLite不需要锁定：假设只有一个客户端。
        

#-------------------------------------------------------------------------------
    def _unlock_table(self, connection):
        """解锁TASKLIST表"""
    
        if self.dbtype=="mysql":
            connection.execute("UNLOCK TABLES")
        elif self.dbtype=="oracle":
            connection.execute("COMMIT")
        elif self.dbtype=="sqlite":
            pass # SQLite不需要锁定：假设只有一个客户端。
        
#-------------------------------------------------------------------------------
    def set_task_finished(self, task, comment="OK"):
        """将任务状态设置为'Finished'"""
        
        conn = self.engine.connect()
        self._lock_table(conn)
        u = self.table_tasklist.update(self.table_tasklist.c.task_id==task["task_id"])
        conn.execute(u, status='Finished', comment=comment)
        self._unlock_table(conn)
        
#-------------------------------------------------------------------------------
    def set_task_error(self, task, comment=None):
        """将任务状态设置为'Error occurred'，并填写相应注释"""
        
        conn = self.engine.connect()
        self._lock_table(conn)
        u = self.table_tasklist.update(self.table_tasklist.c.task_id==task["task_id"])
        conn.execute(u, status='Error occurred', comment=comment)
        self._unlock_table(conn)
