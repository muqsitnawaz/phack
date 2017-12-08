from watchdog.observers import Observer  
from watchdog.events import PatternMatchingEventHandler
from datetime import datetime
from subprocess import Popen, PIPE
import psycopg2
import logging
import threading
import pathlib
import json
import time
import os
import re

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
	streamformatter = logging.Formatter(
		fmt='%(levelname)s\t: %(asctime)s %(threadName)s@%(funcName)s:\t\t%(message)s', 
		datefmt='%H:%M:%S'
	)
	filehandler_dbg.setFormatter(streamformatter)
	logger.addHandler(filehandler_dbg)

def load_config():
	global config
	try:
		config = json.load(open(os.getcwd()+"/config.json"))
	except (ValueError) as error:
		logger.warning("Config Error: {}".format(error))
		print("Config Error: {}".format(error))
		quit()
	finally:
		logger.info("Config file loaded.")

def init_database(creds):
	global db_conn
	try:
		# connect to the PostgreSQL server
		print('Connecting to the PostgreSQL database...')
		db_conn = psycopg2.connect("dbname={} user={} password={}".format(
			creds["dbname"], creds["username"], creds["password"]
		))
		cur = db_conn.cursor()
	
		# execute a statement
		print('PostgreSQL database version:')
		cur.execute('SELECT version()')
 
		# display the PostgreSQL database server version
		db_version = cur.fetchone()
		print(db_version)

		# modifying tables
		if config["drop_tables"]:
			cur.execute(tables.drop_command())
			print('Dropping tables done.')

		if config["create_tables"]:
			commands = tables.create_commands()
			for command in commands:
				cur.execute(command)
			print('Creating tables done.')
		 
		# commiting changes
		cur.close()
		db_conn.commit()
	except (Exception, psycopg2.DatabaseError) as error:
		logger.warning(error)
		print("Database error: {}".format(error))
		quit()
	finally:
		logger.info('Database setup successfull.')

def load_exploits():
	files = []
	for filepath in pathlib.Path(os.getcwd()+'/exploits/').glob('**/*'):
		files.append(str(filepath.absolute()))

	rows = list(map(lambda x : (x, True, datetime.now()), files))
	
	try:
		sql = """INSERT INTO exploits (name, enabled, created_at) VALUES (%s,%s,%s);"""
		cur = db_conn.cursor()
		cur.executemany(sql, rows)
		cur.close()
		db_conn.commit()	
	except (Exception, psycopg2.DatabaseError) as error:
		logger.warning(error)
		print(error)
	finally:
		logger.info('Existing exploits uploaded to database.')
		print('Existing exploits uploaded to database.')

class NewExploitHandler(PatternMatchingEventHandler):
	pattern = [".*"]

	def on_created(self, e):
		logger.debug(e.src_path + ' was created.')
		print('[DEBUG] New exploit: '.format(e.src_path))

		# Uploading to database
		try:
			sql = """INSERT INTO exploits (name, enabled, created_at) VALUES (%s,%s,%s);"""
			dt = datetime.now()
			cur = db_conn.cursor()
			cur.execute(sql, (e.src_path, 't', dt, ))
			cur.close()
			db_conn.commit()
		except (Exception, psycopg2.DatabaseError) as error:
			logger.warning(error)
			print(error)
		finally:
			logger.info('Exploit {} uploaded to database'.format(e.src_path))
		

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
		self.round_dur = round_dur
		self.procs = []
		self.round_id = 0

	def run_exploits(self):
		# Incr round id
		self.round_id += 1

		logger.debug('Running exploits in round {}'.format(self.round_id))
		print('[DEBUG] Running exploits in round {}'.format(self.round_id))

		# Query database for enabled exploits
		cur = db_conn.cursor()
		cur.execute("SELECT name FROM exploits WHERE enabled='t';")
		exploits = cur.fetchall()
		print('[DEBUG] Enabled exploits: ',exploits)
		cur.close()

		# Run exploits
		for ename in exploits:
			for team in config["teams"]:
				proc = Popen([ename[0], team["host"], team["port"]], stdout=PIPE, stderr=PIPE)
				start_at = datetime.now()
			
				# Add to processes list
				self.procs.append((proc, start_at))
				logger.debug('{} was added to active processes list'.format(' '.join(proc.args)))

		# Insert execution trace entry to database
		rows = list(map(lambda x : (self.round_id, x[0].args[0], ' '.join(x[0].args[1:]), x[1]), self.procs))	
		
		try:
			sql = """INSERT INTO traces (round, name, args, start_at) VALUES (%s,%s,%s,%s);"""
			cur = db_conn.cursor()
			cur.executemany(sql, rows)
			cur.close()
			db_conn.commit()	
		except (Exception, psycopg2.DatabaseError) as error:
			logger.warning(error)
			print(error)
		finally:
			logger.info('Exploits uploaded to database.')
			
			
	def kill_exploits(self):
		logger.info('Killing exploits from round {}'.format(self.round_id))	
		print('[DEBUG] Killing exploits from round {}'.format(self.round_id))

		rows = []
		for proc_exec in self.procs:
			proc = proc_exec[0]
			start_at = proc_exec[1]
			timeout = 'f'
			
			logger.debug('Analyzing exploit: {}'.format(proc.args[0]))

			# Terminate exploits still in execution and set flag
			if proc.poll() != 0:
				timeout = 't'
				proc.terminate()
				logger.info("Terminating process: ({}, {})".format(proc.args[0],proc.pid))
				print('[DEBUG] Process {} timed out.'.format(proc.args[0]))
			
			# Get stdout and stderr
			ename = proc.args[0]
			eout = str(proc.stdout.read(), "utf-8")
			eerr = str(proc.stderr.read(), "utf-8")
	
			logger.debug(ename+"->stdout: "+eout)
			logger.debug(ename+"->stderr: "+eerr)

			rows.append((eout, eerr, timeout, start_at))

		# Put execution trace in database
		try:
			sql = """UPDATE traces SET stdout = %s, stderr = %s, timeout = %s WHERE start_at = %s;"""
			cur = db_conn.cursor()
			cur.executemany(sql, rows)
			cur.close()
			db_conn.commit()
		except (Exception, psycopg2.DatabaseError) as error:
			logger.warning(error)
			print(error)
		finally:
			logger.info('Execution traces updated in database.')
		
		# Removing all processes from the list
		self.procs = []

	def run(self):
		logger.debug('Scheduler thread started.')	
		print("Scheduler thread started.")

		while True:
			time.sleep(self.round_dur)
			self.kill_exploits()
			self.run_exploits()

if __name__ == '__main__':
	setup_logger()
	load_config()
	init_database(config["db_creds"])

	load_exploits()
	
	wthread = WatchThread(config["exploits_dir"])
	wthread.start()

	sthread = SchedulerThread(config["round_dur"])
	sthread.start()
