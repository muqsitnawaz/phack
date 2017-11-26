from watchdog.observers import Observer  
from watchdog.events import PatternMatchingEventHandler
from datetime import datetime
import http.server
import psycopg2
import logging
import threading
import json
import time
import os

import tables

# Globals
logger = None
config = None
db_conn = None

def setup_logger():
	global logger
	logger = logging.getLogger('phack')
	logger.setLevel('DEBUG')
	filehandler_dbg = logging.FileHandler(logger.name + '-debug.log', mode='w')
	filehandler_dbg.setLevel('DEBUG')
	streamformatter = logging.Formatter(fmt='%(levelname)s\t:\t%(asctime)s\tt%(threadName)s@%(funcName)s:\t\t%(message)s', datefmt='%H:%M:%S')
	filehandler_dbg.setFormatter(streamformatter)
	logger.addHandler(filehandler_dbg)

def load_config():
	global config
	try:
		config = json.load(open(os.getcwd()+"/config.json"))
	except (Exception) as error:
		logger.warning(error)
	finally:
		logger.info("Config file loaded.")

def init_database():
	""" Connect to the PostgreSQL database server """
	global db_conn
	try:
		# connect to the PostgreSQL server
		print('Connecting to the PostgreSQL database...')
		db_conn = psycopg2.connect("dbname=ctf user=root password=M$sk3dv1p3r")
		cur = db_conn.cursor()
	
		# execute a statement
		print('PostgreSQL database version:')
		cur.execute('SELECT version()')
 
		# display the PostgreSQL database server version
		db_version = cur.fetchone()
		print(db_version)

		# modifying tables
		if config["drop_tables"] == "True":
			cur.execute(tables.drop_command())
			print('Dropping tables done.')

		if config["create_tables"] == "True":
			commands = tables.create_commands()
			for command in commands:
				cur.execute(command)
			print('Creating tables done.')
		 
		# commiting changes
		cur.close()
		db_conn.commit()
	except (Exception, psycopg2.DatabaseError) as error:
		logger.warning(error)
	finally:
		logger.info('Database setup successfull.')

class NewExploitHandler(PatternMatchingEventHandler):
	pattern = [".*"]

	def on_created(self, e):
		global db_conn
		logger.debug(e.src_path + ' was created.')
		print('Debug:', e.src_path)

		# Uploading to database
		try:
			sql = """INSERT INTO exploits(name, enabled, created_at) VALUES(%s,%s,%s);"""
			name = e.src_path[e.src_path.rfind('/')+1:]
			dt = datetime.now()
			cur = db_conn.cursor()
			cur.execute(sql, (name, 't', dt, ))
			cur.close()
			db_conn.commit()
		except (Exception, psycopg2.DatabaseError) as error:
			logger.warning(error)
			print(error)
		finally:
			logger.info('Exploit ' + e.src_path + ' uploaded to database')
		

class WatchThread(threading.Thread):
	def __init__(self):
		threading.Thread.__init__(self)
	def run(self):
		global config
		observer = Observer()
		observer.schedule(NewExploitHandler(), config["exploits_dir"])
		observer.start()
	
		logger.debug('Watch thread started.')	
		print("Watch thread started.")

		try:
			while True:
				time.sleep(1)
		except KeyboardInterrupt:
			observer.stop()

		observer.join()

def init_watch():
	wthread = WatchThread()
	wthread.start()

if __name__ == '__main__':
	setup_logger()
	load_config()
	init_database()
	init_watch()
	print('Done.')
