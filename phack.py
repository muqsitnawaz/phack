from watchdog.observers import Observer  
from watchdog.events import PatternMatchingEventHandler
from datetime import datetime
from subprocess import Popen, PIPE
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
	streamformatter = logging.Formatter(fmt='%(levelname)s\t: %(asctime)s %(threadName)s@%(funcName)s:\t\t%(message)s', datefmt='%H:%M:%S')
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
		logger.debug(e.src_path + ' was created.')
		print('Debug [New Exploit]: ', e.src_path)

		# Uploading to database
		try:
			sql = """INSERT INTO exploits (name, enabled, created_at) VALUES (%s,%s,%s);"""
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
	def __init__(self, exploits_dir):
		threading.Thread.__init__(self)
		self.exploits_dir = exploits_dir
	def run(self):
		observer = Observer()
		observer.schedule(NewExploitHandler(), self.exploits_dir)
		observer.start()
	
		logger.debug('Watch thread started.')	
		print("Watch thread started.")

		try:
			while True:
				time.sleep(1)
		except KeyboardInterrupt:
			observer.stop()

		observer.join()

class SchedulerThread(threading.Thread):
	def __init__(self, round_dur):
		threading.Thread.__init__(self)
		self.round_dur = int(round_dur)
		self.procs = []
		self.round_id = 0

	def run_exploits(self):
		# Incr round id
		self.round_id += 1

		logger.debug('Running exploits in round ' + str(self.round_id))

		# Quering database for exploits
		cur = db_conn.cursor()
		cur.execute("SELECT name FROM exploits WHERE enabled='t';")
		exploits = cur.fetchall()
		print('Debug [Enabled Exploits]: ',exploits)
		cur.close()

		# Running exploits
		for ename in exploits:
			proc = Popen(["./exploits/"+ename[0]], stdout=PIPE, stderr=PIPE)
			
			# Query database for exploits
			try:
				start_at = datetime.now()
				sql = """INSERT INTO traces (round, name, start_at) VALUES (%s,%s,%s);"""
				cur = db_conn.cursor()
				cur.execute(sql, (self.round_id, ename[0], start_at))
				cur.close()
				db_conn.commit()	
			except (Exception, psycopg2.DatabaseError) as error:
				logger.warning(error)
				print(error)
			finally:
				logger.info('Execution entry inserted in database.')
			
			# Add to processes list
			self.procs.append((proc, start_at))
	
	def kill_exploits(self):
		logger.debug('Killing exploits from round ' + str(self.round_id))

		# Get exploits from last round
		for proc_exec in self.procs:
			proc = proc_exec[0]
			start_at = proc_exec[1]
			print('Debug [Exploit pid]: ', proc.pid)
			
			eout = str(proc.stdout.read(), "utf-8")
			eerr = str(proc.stderr.read(), "utf-8")

			logger.debug("Exploit: "+proc.args[0])
			logger.debug("\tstdout: "+eout)
			logger.debug("\tstderr: "+eerr)

			# Terminate exploits still in execution
			if proc.poll() != 0:
				proc.terminate()
			
			# Remove exploits from list
			self.procs.remove(proc_exec)

			# Put execution trace in database
			try:
				sql = """UPDATE traces SET stdout = %s, stderr = %s WHERE start_at = %s;"""
				cur = db_conn.cursor()
				cur.execute(sql, (eout, eerr, start_at))
				cur.close()
				db_conn.commit()
			except (Exception, psycopg2.DatabaseError) as error:
				logger.warning(error)
				print(error)
			finally:
				logger.info('Execution entry updated in database.')

	def run(self):
		print("Scheduler thread started.")
		while True:
			time.sleep(self.round_dur)
			self.kill_exploits()
			self.run_exploits()

if __name__ == '__main__':
	setup_logger()
	load_config()
	init_database()
	
	wthread = WatchThread(config["exploits_dir"])
	wthread.start()

	sthread = SchedulerThread(config["round_dur"])
	sthread.start()
