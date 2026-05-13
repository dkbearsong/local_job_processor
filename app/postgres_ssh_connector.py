"""
PostgreSQL SSH Connector Module

This module provides functionality to connect to a remote PostgreSQL database
via SSH tunnel and execute SELECT queries.
"""

import os
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor
from sshtunnel import SSHTunnelForwarder
import logging
from sshtunnel import BaseSSHTunnelForwarderError
from paramiko import RSAKey, ECDSAKey, Ed25519Key
from paramiko.ssh_exception import SSHException

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_ssh_key(key_path: str):
    """
    Load SSH private key from file.
    
    Args:
        key_path (str): Path to SSH private key file
    
    Returns:
        paramiko key object or None if file doesn't exist
    """
    if not key_path or not os.path.exists(key_path):
        return None
    
    try:
        # Try different key types
        key_types = [RSAKey, ECDSAKey, Ed25519Key]
        for key_type in key_types:
            try:
                return key_type.from_private_key_file(key_path)
            except SSHException:
                continue
        
        logger.warning(f"Could not load SSH key from {key_path} with standard key types")
        return None
    except Exception as e:
        logger.warning(f"Error loading SSH key from {key_path}: {str(e)}")
        return None

def execute_query_on_remote_db(
    ssh_host: str,
    ssh_port: int,
    ssh_username: str,
    ssh_password: str,
    ssh_key_path: str,
    db_host: str,
    db_port: int,
    db_name: str,
    db_user: str,
    db_password: str,
    query: str
):
    """
    Execute a SELECT query on a remote PostgreSQL database via SSH tunnel.
    
    Args:
        ssh_host (str): SSH server hostname or IP
        ssh_port (int): SSH server port (default: 22)
        ssh_username (str): SSH username
        ssh_password (str): SSH password (optional if using key)
        ssh_key_path (str): Path to SSH private key file (optional)
        db_host (str): PostgreSQL host (default: "localhost")
        db_port (int): PostgreSQL port (default: 5432)
        db_name (str): Database name
        db_user (str): Database username
        db_password (str): Database password
        query (str): SQL SELECT query to execute
    
    Returns:
        list: Query results as list of tuples
    """
    
    # Validate required parameters
    if not query:
        raise ValueError("Query parameter is required")
    
    if not db_name or not db_user or not db_password:
        raise ValueError("Database credentials (name, user, password) are required")
    
    # Validate SSH authentication method
    if not ssh_password and not ssh_key_path:
        raise ValueError("Either SSH password or SSH key path must be provided")
    
    # Prepare SSH tunnel configuration
    ssh_config = {
        'ssh_address_or_host': (ssh_host, ssh_port),
        'ssh_username': ssh_username,
        'remote_bind_address': (db_host, db_port),
        'allow_agent': False  # Disable SSH agent to avoid ssh-agent errors
    }
    
    # Add SSH password or key configuration
    if ssh_password:
        ssh_config['ssh_password'] = ssh_password
    elif ssh_key_path:
        # Load the SSH key file properly
        ssh_key = load_ssh_key(ssh_key_path)
        if ssh_key:
            ssh_config['ssh_pkey'] = ssh_key
        else:
            raise ValueError(f"Could not load SSH key from {ssh_key_path}. Ensure the file exists and is a valid private key.")
    
    try:
        # Create SSH tunnel
        logger.info(f"Creating SSH tunnel to {ssh_host}:{ssh_port}")
        tunnel = SSHTunnelForwarder(**ssh_config)
        
        # Start the tunnel
        logger.info("Attempting to establish SSH tunnel...")
        tunnel.start()
        logger.info("SSH tunnel established successfully")
        
        # Connect to PostgreSQL through the tunnel
        connection_params = {
            'host': '127.0.0.1',
            'port': tunnel.local_bind_port,
            'database': db_name,
            'user': db_user,
            'password': db_password
        }
        
        logger.info(f"Connecting to PostgreSQL database: {db_name}")
        conn = psycopg2.connect(**connection_params)
        
        # Execute query
        logger.info(f"Executing query: {query[:100]}...")
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(query)
        
        # Fetch results
        results = cursor.fetchall()
        
        # Clean up
        cursor.close()
        conn.close()
        tunnel.stop()
        
        logger.info(f"Query executed successfully. Rows returned: {len(results)}")
        return [dict(row) for row in results]
   
    except BaseSSHTunnelForwarderError as e:
        error_msg = (
            f"SSH tunnel connection failed. Common causes:\n"
            f"- Incorrect SSH host or port: {ssh_host}:{ssh_port}\n"
            f"- Invalid SSH credentials (username/password or key)\n"
            f"- SSH server not accessible or firewall blocking connection\n"
            f"- SSH key permissions (should be 600)\n"
            f"Error details: {str(e)}"
        )
        logger.error(error_msg)
        raise ConnectionError(error_msg) from e
    
    except psycopg2.OperationalError as e:
        error_msg = (
            f"PostgreSQL connection failed. Possible causes:\n"
            f"- Database name '{db_name}' does not exist\n"
            f"- Invalid database credentials (user/password)\n"
            f"- Database server not accessible\n"
            f"- Connection timeout\n"
            f"Error details: {str(e)}"
        )
        logger.error(error_msg)
        raise ConnectionError(error_msg) from e
    
    except psycopg2.Error as e:
        error_msg = (
            f"PostgreSQL database error. Query execution failed:\n"
            f"- Invalid SQL syntax in query\n"
            f"- Insufficient permissions for query execution\n"
            f"- Database connection issues\n"
            f"Error details: {str(e)}"
        )
        logger.error(error_msg)
        raise RuntimeError(error_msg) from e
    
    except Exception as e:
        error_msg = (
            f"Unexpected error occurred while connecting to database:\n"
            f"- Error type: {type(e).__name__}\n"
            f"- Error details: {str(e)}\n"
            f"- Check that all connection parameters are correct\n"
            f"- Verify network connectivity to SSH and database servers"
        )
        logger.error(error_msg)
        raise

def execute_query_with_env_vars(query: str):
    """
    Execute a SELECT query using environment variables for configuration.
    
    Args:
        query (str): SQL SELECT query to execute
    
    Returns:
        list: Query results as list of tuples
    """
    
    # Read configuration from environment variables
    ssh_host = os.getenv('SSH_HOST')
    ssh_port = int(os.getenv('SSH_PORT', 22))
    ssh_username = os.getenv('SSH_USERNAME')
    ssh_password = os.getenv('SSH_PASSWORD')
    ssh_key_path = os.getenv('SSH_KEY_PATH')
    
    db_host = os.getenv('DB_HOST', 'localhost')
    db_port = int(os.getenv('DB_PORT', 5432))
    db_name = os.getenv('DB_NAME')
    db_user = os.getenv('DB_USER')
    db_password = os.getenv('DB_PASSWORD')
    
    # Validate required environment variables
    required_vars = [
        'SSH_HOST', 'SSH_USERNAME', 'DB_NAME', 'DB_USER', 'DB_PASSWORD'
    ]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {missing_vars}")
    
    return execute_query_on_remote_db(
        ssh_host=ssh_host or "",
        ssh_port=ssh_port,
        ssh_username=ssh_username or "",
        ssh_password=ssh_password or "",
        ssh_key_path=ssh_key_path or "",
        db_host=db_host,
        db_port=db_port,
        db_name=db_name or "",
        db_user=db_user or "",
        db_password=db_password or "",
        query=query
    )

# Testing method

def main ():
    sql_query = """
    SELECT *
    FROM job
    LIMIT 10;
    """
    print(execute_query_with_env_vars(sql_query))

if __name__ == "__main__":
    main()