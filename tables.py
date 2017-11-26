def drop_command():
    """ create tables in the PostgreSQL database"""
    return """DROP TABLE IF EXISTS exploits, flags, traces;"""

def create_commands():
    """ create tables in the PostgreSQL database"""
    commands = (
        """
        CREATE TABLE exploits (
            exploit_id SERIAL PRIMARY KEY,
            name VARCHAR(10) NOT NULL UNIQUE,
            comment VARCHAR(255),
            enabled BOOLEAN NOT NULL DEFAULT 't',
            created_at TIMESTAMP NOT NULL
        )
        """,
        """ CREATE TABLE flags (
                flag_id SERIAL PRIMARY KEY,
                flag VARCHAR(255) NOT NULL,
                points INT,
                submitted BOOLEAN NOT NULL DEFAULT 'f',
                created_at TIMESTAMP,
                submitted_at TIMESTAMP
        )
        """,
        """
        CREATE TABLE traces (
                exec_id SERIAL PRIMARY KEY,
                name VARCHAR(10) NOT NULL,
                start_at TIMESTAMP,
                end_at TIMESTAMP,
                stdout VARCHAR(65536),
                stderr VARCHAR(65536)
        )
        """)
    return commands;

