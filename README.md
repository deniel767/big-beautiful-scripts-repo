# Big Beautiful Scripts Repo 🛠️

A curated collection of standalone Python utilities and automation pieces.

---

## 🎛️ Suite Architecture & Repository Navigation

Only .env file is shared between scripts, otherwise all are standalone.

```text
├── README.md                 
├── .env.example              # Blueprint for local environment variables
├── requirements.txt          # Dependencies
│
├── all_the_words.py          # Module 1: Desktop Dictionary
└── IBKR_api.py               # Module 2: Interactive Brokers Data Broker


1. all_the_words.py — Multi-Language Desktop Dictionary with Local Caching
A lightweight Tkinter desktop application for dictionary lookups and translations that caches results locally to minimize external API hits.

Tech Stack: Python 3.11, Tkinter, Requests, Pickle, Nest-Asyncio

 - Features overview and highlighted details
 
Uses pickle to cache/save previously looked up words. Does not use URL calls if word is already saved.

Can support multiple languages, but each Language needs to be hardcoded since request URL changes with Language abbreviation

2. IBKR_api.py — Interactive Brokers Data Pipeline
A basic module for interacting with the Interactive Brokers native Python API (EClient/EWrapper).
Main usage is historical stock data requests and trade execution report request.

Tech Stack: Python 3.11, ibapi, ib_insync, Pandas, ElementTree (XML)

 - Features overview and highlighted details
 
Deals with most of the rather annoying features IBKR API is known for.
 - ignores most of the not useful error codes the API throws at you
 - added timeout checks + built-in delays at critical points - API can take its time returning data and a few seconds can make the difference of empty versus full dataframe
 - helper functions for finding contact == instrument details since API needs lot of details passed to return anything