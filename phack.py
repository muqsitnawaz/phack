import http.server
import psycopg2
import logging
import threading
import json
import tables
import os

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
	streamformatter = logging.Formatter(fmt='%(levelname)s : %(asctime)s\t%(threadName)s@%(funcName)s:\t%(message)s', datefmt='%H:%M:%S')
	filehandler_dbg.setFormatter(streamformatter)
	logger.addHandler(filehandler_dbg)

def load_config():
	global config
	try:
		config = json.load(open(os.getcwd()+"/config.json"))
	except (Exception) as error:
		logger.warning(error)
		print(error)
	finally:
		logger.debug("Config file loaded.")

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
		print(error)
	finally:
		logger.debug('Database setup successfull.')

class ServerThread(threading.Thread):
	def __init__(self):
		threading.Thread.__init__(self)
		self.ip = config["ip"]
		self.port = int(config["port"])
	def run(self):
		handler = http.server.SimpleHTTPRequestHandler
		httpd = http.server.HTTPServer((self.ip, self.port), handler)
		print("Serving at port", self.port)
		httpd.serve_forever()
		logger.debug('Server setup successfull.')

serv = None
def init_server():
	serv = ServerThread()
	serv.start()

if __name__ == '__main__':
	setup_logger()
	load_config()
	init_database()
	init_server()
	print('Done.')
