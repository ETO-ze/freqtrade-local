@echo off
cd /d D:\Playground\freqtrade-local
py -m streamlit run D:\Playground\freqtrade-local\apps\streamlit\strategy_debug_lab.py --server.address 127.0.0.1 --server.port 8502


