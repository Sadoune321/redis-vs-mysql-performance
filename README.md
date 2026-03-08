# Redis vs MySQL Performance Comparison

This project benchmarks the execution time of **Redis** and **MySQL** for common database operations.
The application is built with **Python** and **Flask** and runs using **Docker** and **Docker Compose**.

## Technologies

* Python
* Flask
* Redis
* MySQL
* Docker
* Docker Compose

## Goal

The goal of this project is to compare the performance of Redis (in-memory database) and MySQL (relational database) by measuring the execution time of CRUD operations.

## Run the Project

Clone the repository:

```
git clone https://github.com/Sadoune321/redis-vs-mysql-performance.git
cd redis-vs-mysql-performance
```

Start the services with Docker Compose:

```
docker-compose up --build
```

The application will start and connect to both Redis and MySQL containers to perform performance tests.

## Author

Sadoune
