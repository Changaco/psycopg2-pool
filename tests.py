from __future__ import absolute_import, division, print_function, unicode_literals

from unittest import TestCase

from psycopg2.errors import ProgrammingError
import psycopg2.extensions as _ext

from psycopg2_pool import ConnectionPool, PoolError


class PoolTests(TestCase):

    def test_getconn(self):
        pool = ConnectionPool(0, 1)
        conn = pool.getconn()

        # Make sure we got an open connection
        assert not conn.closed

        # Try again. We should get an error, since we only allowed one connection.
        with self.assertRaises(PoolError):
            pool.getconn()

        # Put the connection back, the return time should be saved
        pool.putconn(conn)
        assert conn in pool.return_times

        # Get the connection back
        new_conn = pool.getconn()
        assert new_conn is conn

    def test_putconn(self):
        pool = ConnectionPool(0, 1)
        conn = pool.getconn()
        assert conn not in pool.idle_connections

        pool.putconn(conn)
        assert conn in pool.idle_connections

    def test_putconn_opens_new_connection_to_comply_with_minconn(self):
        pool = ConnectionPool(1, 1, idle_timeout=0)
        conn = pool.getconn()
        assert conn not in pool.idle_connections
        assert len(pool.idle_connections) == 0

        conn.close()
        pool.putconn(conn)

        # This connection shouldn't be put in the idle queue because it's closed
        assert conn not in pool.idle_connections

        # But we should still have *a* connection available
        assert len(pool.idle_connections) == 1

    def test_getconn_closed(self):
        pool = ConnectionPool(0, 1)
        conn = pool.getconn()
        pool.putconn(conn)

        # Close the connection, it should still be in the pool
        conn.close()
        assert conn in pool.idle_connections

        # The connection should be discarded by getconn
        new_conn = pool.getconn()
        assert new_conn is not conn
        assert conn not in pool.idle_connections
        assert conn not in pool.return_times
        assert conn.closed

    def test_getconn_expired(self):
        pool = ConnectionPool(0, 1, idle_timeout=30)
        conn = pool.getconn()

        # Expire the connection
        pool.putconn(conn)
        pool.return_times[conn] -= 60

        # Connection should be discarded
        new_conn = pool.getconn()
        assert new_conn is not conn
        assert conn not in pool.idle_connections
        assert conn not in pool.return_times
        assert conn.closed

    def test_putconn_errorState(self):
        pool = ConnectionPool(0, 1)
        conn = pool.getconn()

        # Get connection into transaction state
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO nonexistent (id) VALUES (1)")
        except ProgrammingError:
            pass

        assert conn.get_transaction_status() != _ext.TRANSACTION_STATUS_IDLE

        pool.putconn(conn)

        # Make sure we got back into the pool and are now showing idle
        assert conn.get_transaction_status() == _ext.TRANSACTION_STATUS_IDLE
        assert conn in pool.idle_connections

    def test_putconn_closed(self):
        pool = ConnectionPool(0, 1)
        conn = pool.getconn()

        # The connection should be open and shouldn't have a return time
        assert not conn.closed
        assert conn not in pool.return_times

        conn.close()

        # Now should be closed
        assert conn.closed

        pool.putconn(conn)

        # The connection should have been discarded
        assert conn not in pool.idle_connections
        assert conn not in pool.return_times

    def test_caching(self):
        pool = ConnectionPool(0, 10)

        # Get a connection to use to check the number of connections
        check_conn = pool.getconn()
        check_conn.autocommit = True  # Being in a transaction hides the other connections.
        # Get a cursor to run check queries with
        check_cursor = check_conn.cursor()

        SQL = """
            SELECT numbackends
              FROM pg_stat_database
             WHERE datname = current_database()
        """
        check_cursor.execute(SQL)

        # Not trying to test anything yet, so hopefully this always works :)
        starting_conns = check_cursor.fetchone()[0]

        # Get a couple more connections
        conn2 = pool.getconn()
        conn3 = pool.getconn()

        assert conn2 != conn3

        # Verify that we have the expected number of connections to the DB server now
        check_cursor.execute(SQL)
        total_cons = check_cursor.fetchone()[0]

        assert total_cons == starting_conns + 2

        # Put the connections back in the pool and verify they don't close
        pool.putconn(conn2)
        pool.putconn(conn3)

        check_cursor.execute(SQL)
        total_cons_after_put = check_cursor.fetchone()[0]

        assert total_cons == total_cons_after_put

        # Get another connection and verify we don't create a new one
        conn4 = pool.getconn()

        # conn4 should be either conn2 or conn3 (we don't care which)
        assert conn4 in (conn2, conn3)

        check_cursor.execute(SQL)
        total_cons_after_get = check_cursor.fetchone()[0]

        assert total_cons_after_get == total_cons

    def test_extraneous_connections_are_discarded(self):
        pool = ConnectionPool(minconn=0, idle_timeout=120)
        # Get multiple connections then put them all back
        conns = [pool.getconn() for i in range(3)]
        for conn in conns:
            pool.putconn(conn)
        # Simulate 1 minute passing
        for conn in conns:
            pool.return_times[conn] -= 60
        # Check out one connection multiple times, we should always get the same one
        last_conn = conns[-1]
        for i in range(len(conns)):
            conn = pool.getconn()
            assert conn is last_conn
            pool.putconn(conn)
        # Simulate another minute passing
        for conn in conns:
            pool.return_times[conn] -= 60
        # Get a connection then return it, the other connections should be
        # discarded by `putconn` because they're too old now
        conn = pool.getconn()
        assert conn is last_conn
        assert list(pool.idle_connections) == conns[:2]
        assert set(pool.return_times) == set(conns[:2])
        pool.putconn(conn)
        assert list(pool.idle_connections) == [conn]
        assert set(pool.return_times) == set([conn])

    def test_clear(self):
        pool = ConnectionPool(0, 10)
        conn1 = pool.getconn()
        conn2 = pool.getconn()
        pool.putconn(conn2)

        assert len(pool.idle_connections) == 1
        assert len(pool.connections_in_use) == 1
        assert not conn1.closed
        assert not conn2.closed

        pool.clear()

        assert conn2.closed
        assert not conn1.closed
        assert len(pool.connections_in_use) == 1
        assert len(pool.idle_connections) == 0
        assert len(pool.return_times) == 0
