PRAGMA foreign_keys = ON;

CREATE TABLE CUSTOMER (
    Customer_ID INTEGER PRIMARY KEY AUTOINCREMENT,
    Name VARCHAR(50) NOT NULL,
    Phone VARCHAR(15) NOT NULL,
    Email VARCHAR(100),
    Address VARCHAR(150)
);

CREATE TABLE PARCEL (
    Parcel_ID INTEGER PRIMARY KEY AUTOINCREMENT,
    Tracking_Number VARCHAR(20) UNIQUE NOT NULL,
    Sender_ID INTEGER NOT NULL,
    Receiver_Name VARCHAR(50) NOT NULL,
    Receiver_Phone VARCHAR(15) NOT NULL,
    Destination VARCHAR(100) NOT NULL,
    Weight DECIMAL(5,2),
    Booking_Date DATE NOT NULL,
    Delivery_Status VARCHAR(30) DEFAULT 'Booked',

    FOREIGN KEY (Sender_ID)
        REFERENCES CUSTOMER(Customer_ID)
);

CREATE TABLE EMPLOYEE (
    Employee_ID INTEGER PRIMARY KEY AUTOINCREMENT,
    Name VARCHAR(50) NOT NULL,
    Phone VARCHAR(15),
    Designation VARCHAR(50)
);

CREATE TABLE DELIVERY_LOG (
    Log_ID INTEGER PRIMARY KEY AUTOINCREMENT,
    Parcel_ID INTEGER NOT NULL,
    Employee_ID INTEGER NOT NULL,
    Status VARCHAR(30) NOT NULL,
    Status_Date DATE NOT NULL,
    Location VARCHAR(100),
    Remarks VARCHAR(150),

    FOREIGN KEY (Parcel_ID)
        REFERENCES PARCEL(Parcel_ID),

    FOREIGN KEY (Employee_ID)
        REFERENCES EMPLOYEE(Employee_ID)
);

CREATE TABLE PAYMENT (
    Payment_ID INTEGER PRIMARY KEY AUTOINCREMENT,
    Parcel_ID INTEGER UNIQUE NOT NULL,
    Amount DECIMAL(10,2) NOT NULL,
    Payment_Date DATE NOT NULL,
    Payment_Method VARCHAR(30),
    Payment_Status VARCHAR(30),

    FOREIGN KEY (Parcel_ID)
        REFERENCES PARCEL(Parcel_ID)
);