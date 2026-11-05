"""
Tests for restocking order API endpoints.
"""
from datetime import datetime

import pytest

import main


@pytest.fixture(autouse=True)
def reset_restocking_orders():
    """Clear the in-memory restocking orders so each test starts empty."""
    main.restocking_orders.clear()
    yield
    main.restocking_orders.clear()


@pytest.fixture
def restocking_items():
    """Two forecast items with different trends, totalling $7,567.50."""
    return [
        {"sku": "WDG-001", "name": "Industrial Widget Type A", "quantity": 150,
         "unit_cost": 12.5, "trend": "increasing"},
        {"sku": "BRG-102", "name": "Steel Bearing Assembly", "quantity": 126,
         "unit_cost": 45.0, "trend": "stable"},
    ]


class TestRestockingEndpoints:
    """Test suite for restocking order endpoints."""

    def test_get_restocking_orders_empty(self, client):
        """Test that no restocking orders exist before any are placed."""
        response = client.get("/api/restocking-orders")
        assert response.status_code == 200
        assert response.json() == []

    def test_create_restocking_order(self, client, restocking_items):
        """Test placing a restocking order within budget."""
        response = client.post("/api/restocking-orders",
                               json={"budget": 10000, "items": restocking_items})
        assert response.status_code == 201

        order = response.json()
        for field in ["id", "order_number", "items", "total_cost", "budget", "status",
                      "created_date", "lead_time_days", "expected_delivery"]:
            assert field in order
        assert order["status"] == "Submitted"
        assert order["order_number"].startswith("RST-")
        assert order["budget"] == 10000
        assert len(order["items"]) == 2

    def test_restocking_order_total_calculation(self, client, restocking_items):
        """Test that the server computes the order total from its items."""
        response = client.post("/api/restocking-orders",
                               json={"budget": 10000, "items": restocking_items})
        order = response.json()

        expected_total = sum(item["quantity"] * item["unit_cost"] for item in restocking_items)
        assert abs(order["total_cost"] - expected_total) < 0.01

    def test_restocking_order_lead_time_is_slowest_item(self, client, restocking_items):
        """Test that lead time is the max across items (increasing=10 beats stable=7)."""
        response = client.post("/api/restocking-orders",
                               json={"budget": 10000, "items": restocking_items})
        assert response.json()["lead_time_days"] == 10

    @pytest.mark.parametrize("trend,expected_days", [
        ("stable", 7),
        ("increasing", 10),
        ("decreasing", 14),
    ])
    def test_restocking_order_lead_time_by_trend(self, client, trend, expected_days):
        """Test the lead time assigned to each demand trend."""
        item = {"sku": "PSU-501", "name": "5V 10A Switching Power Supply",
                "quantity": 10, "unit_cost": 18.99, "trend": trend}
        response = client.post("/api/restocking-orders", json={"budget": 1000, "items": [item]})
        assert response.status_code == 201
        assert response.json()["lead_time_days"] == expected_days

    def test_restocking_order_expected_delivery(self, client, restocking_items):
        """Test that expected delivery is the created date plus the lead time."""
        response = client.post("/api/restocking-orders",
                               json={"budget": 10000, "items": restocking_items})
        order = response.json()

        created = datetime.fromisoformat(order["created_date"])
        expected = datetime.fromisoformat(order["expected_delivery"])
        assert (expected - created).days == order["lead_time_days"]

    def test_restocking_order_over_budget(self, client, restocking_items):
        """Test that an order exceeding the budget is rejected."""
        response = client.post("/api/restocking-orders",
                               json={"budget": 5000, "items": restocking_items})
        assert response.status_code == 400
        assert "budget" in response.json()["detail"].lower()

    def test_restocking_order_empty_items(self, client):
        """Test that an order with no items is rejected."""
        response = client.post("/api/restocking-orders", json={"budget": 5000, "items": []})
        assert response.status_code == 400
        assert "detail" in response.json()

    def test_restocking_order_zero_quantity(self, client, restocking_items):
        """Test that an item with zero quantity is rejected."""
        restocking_items[0]["quantity"] = 0
        response = client.post("/api/restocking-orders",
                               json={"budget": 10000, "items": restocking_items})
        assert response.status_code == 400
        assert "quantit" in response.json()["detail"].lower()

    def test_restocking_order_missing_fields(self, client):
        """Test that a malformed request fails validation."""
        response = client.post("/api/restocking-orders", json={"items": []})
        assert response.status_code == 422

    def test_get_restocking_orders_newest_first(self, client, restocking_items):
        """Test that placed orders are listed newest first."""
        first = client.post("/api/restocking-orders",
                            json={"budget": 10000, "items": restocking_items}).json()
        second = client.post("/api/restocking-orders",
                             json={"budget": 10000, "items": restocking_items[:1]}).json()

        response = client.get("/api/restocking-orders")
        assert response.status_code == 200

        data = response.json()
        assert [o["id"] for o in data] == [second["id"], first["id"]]
        assert data[0]["order_number"] != data[1]["order_number"]
