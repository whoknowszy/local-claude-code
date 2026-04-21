"""Tests for client tracking with heartbeat-based liveness."""

import time
import threading

from lccg.middleware.client_tracker import ClientTracker


class TestClientTrackerRegister:
    def test_register_returns_client_id(self):
        tracker = ClientTracker()
        client_id = tracker.register(pid=12345, hostname="myhost")
        assert isinstance(client_id, str)
        assert len(client_id) > 0

    def test_register_stores_client_info(self):
        tracker = ClientTracker()
        client_id = tracker.register(pid=12345, hostname="myhost")
        clients = tracker.list_clients()
        assert len(clients) == 1
        assert clients[0]["client_id"] == client_id
        assert clients[0]["pid"] == 12345
        assert clients[0]["hostname"] == "myhost"
        assert "connected_at" in clients[0]
        assert "last_heartbeat" in clients[0]

    def test_register_multiple_clients(self):
        tracker = ClientTracker()
        id1 = tracker.register(pid=111, hostname="host1")
        id2 = tracker.register(pid=222, hostname="host2")
        assert id1 != id2
        assert tracker.active_count() == 2


class TestClientTrackerDeregister:
    def test_deregister_removes_client(self):
        tracker = ClientTracker()
        client_id = tracker.register(pid=12345, hostname="myhost")
        assert tracker.active_count() == 1
        tracker.deregister(client_id)
        assert tracker.active_count() == 0

    def test_deregister_unknown_client_is_noop(self):
        tracker = ClientTracker()
        tracker.deregister("nonexistent-id")  # should not raise
        assert tracker.active_count() == 0

    def test_deregister_returns_true_if_found(self):
        tracker = ClientTracker()
        client_id = tracker.register(pid=12345, hostname="myhost")
        assert tracker.deregister(client_id) is True

    def test_deregister_returns_false_if_not_found(self):
        tracker = ClientTracker()
        assert tracker.deregister("nonexistent-id") is False


class TestClientTrackerHeartbeat:
    def test_heartbeat_updates_last_heartbeat_time(self):
        tracker = ClientTracker()
        client_id = tracker.register(pid=12345, hostname="myhost")
        info = tracker.list_clients()[0]
        old_hb = info["last_heartbeat"]
        time.sleep(0.01)
        tracker.heartbeat(client_id)
        info = tracker.list_clients()[0]
        assert info["last_heartbeat"] > old_hb

    def test_heartbeat_unknown_client_returns_false(self):
        tracker = ClientTracker()
        assert tracker.heartbeat("nonexistent-id") is False

    def test_heartbeat_known_client_returns_true(self):
        tracker = ClientTracker()
        client_id = tracker.register(pid=12345, hostname="myhost")
        assert tracker.heartbeat(client_id) is True


class TestClientTrackerActiveCount:
    def test_active_count_after_operations(self):
        tracker = ClientTracker()
        assert tracker.active_count() == 0
        id1 = tracker.register(pid=111, hostname="h1")
        assert tracker.active_count() == 1
        id2 = tracker.register(pid=222, hostname="h2")
        assert tracker.active_count() == 2
        tracker.deregister(id1)
        assert tracker.active_count() == 1
        tracker.deregister(id2)
        assert tracker.active_count() == 0


class TestClientTrackerHeartbeatTimeout:
    def test_stale_clients_are_cleaned_up(self):
        tracker = ClientTracker(heartbeat_timeout=0.05)
        tracker.register(pid=111, hostname="h1")
        assert tracker.active_count() == 1
        # Wait for timeout
        time.sleep(0.1)
        # Cleanup stale clients
        tracker.cleanup_stale()
        assert tracker.active_count() == 0

    def test_heartbeated_clients_survive_cleanup(self):
        tracker = ClientTracker(heartbeat_timeout=0.1)
        id1 = tracker.register(pid=111, hostname="h1")
        time.sleep(0.05)
        tracker.heartbeat(id1)  # refresh heartbeat
        tracker.cleanup_stale()
        assert tracker.active_count() == 1

    def test_mixed_stale_and_active_clients(self):
        tracker = ClientTracker(heartbeat_timeout=0.05)
        id1 = tracker.register(pid=111, hostname="h1")
        id2 = tracker.register(pid=222, hostname="h2")
        time.sleep(0.03)
        tracker.heartbeat(id2)  # only id2 gets heartbeat
        time.sleep(0.03)
        tracker.cleanup_stale()
        assert tracker.active_count() == 1
        clients = tracker.list_clients()
        assert clients[0]["client_id"] == id2

    def test_cleanup_stale_returns_count_of_removed(self):
        tracker = ClientTracker(heartbeat_timeout=0.05)
        tracker.register(pid=111, hostname="h1")
        tracker.register(pid=222, hostname="h2")
        time.sleep(0.1)
        removed = tracker.cleanup_stale()
        assert removed == 2


class TestClientTrackerThreadSafety:
    def test_concurrent_register_and_deregister(self):
        tracker = ClientTracker()
        errors = []

        def register_and_deregister(start_id):
            try:
                cid = tracker.register(pid=start_id, hostname=f"h{start_id}")
                tracker.deregister(cid)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=register_and_deregister, args=(i,)) for i in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert tracker.active_count() == 0
