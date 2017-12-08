def drop_command():
    """ create tables in the PostgreSQL database"""
    return """DROP TABLE IF EXISTS exploits, flags, traces;"""

def create_commands():
    """ create tables in the PostgreSQL database"""
    commands = (
        """
        CREATE TABLE exploits (
            exploit_id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL UNIQUE,
            enabled BOOLEAN NOT NULL DEFAULT 't',
            created_at TIMESTAMP NOT NULL
        )
        """,
        """ CREATE TABLE flags (
                flag_id SERIAL PRIMARY KEY,
								exploit_round INT NOT NULL,
								exploit_name VARCHAR(255) NOT NULL,
								exploit_start_at TIMESTAMP NOT NULL,
                flags VARCHAR(255) NOT NULL,
                points INT DEFAULT 1,
                submitted BOOLEAN DEFAULT 'f',
                created_at TIMESTAMP,
                submitted_at TIMESTAMP
        )
        """,
        """
        CREATE TABLE traces (
                exec_id SERIAL PRIMARY KEY,
								round INT NOT NULL,
                name VARCHAR(255) NOT NULL,
                start_at TIMESTAMP,
								args VARCHAR(255),
                timeout BOOLEAN DEFAULT 'f',
                stdout VARCHAR(65536),
                stderr VARCHAR(65536)
        )
        """)
    return commands;

