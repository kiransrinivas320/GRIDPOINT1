# GRIDPOINT

### Demand-Driven Warehouse Location Optimization Platform

GRIDPOINT is a logistics optimization platform designed to answer a simple but important question:

> **Where should a warehouse be located to serve demand efficiently and minimize delivery cost?**

GRIDPOINT allows users to provide neighborhood-level demand data and automatically analyze suitable warehouse locations based on demand, geographic distance, delivery cost, warehouse capacity, and maximum delivery radius.

---

## 🚀 What GRIDPOINT Does

GRIDPOINT transforms raw neighborhood demand data into an optimized warehouse network.

Users can:

- Upload a CSV containing neighborhood demand data
- Enter demand data manually
- Visualize demand locations on an interactive map
- Select the number of warehouses
- Set delivery cost per kilometer
- Set maximum delivery radius
- Set warehouse capacity
- Optimize warehouse locations
- Automatically assign neighborhoods to warehouses
- Compare baseline and optimized delivery costs
- View delivery distances and estimated travel times
- Visualize warehouse-to-neighborhood delivery routes
- Analyze the resulting logistics network

---

## 🧠 How GRIDPOINT Works

The system evaluates possible warehouse locations using the provided neighborhood data.

For each candidate warehouse configuration, GRIDPOINT considers:

- Geographic distance
- Number of customer orders
- Delivery cost per kilometer
- Warehouse capacity
- Maximum delivery radius

The optimization objective is based on:

```text
Delivery Cost = Distance × Orders × Cost per Kilometer