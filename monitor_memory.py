#!/usr/bin/env python3
"""
Memory monitoring script for SharewareZ application.
Logs memory usage statistics every 5 seconds with detailed timestamps.
"""

import psutil
import time
import csv
import os
import sys
from datetime import datetime
import argparse

def get_sharewarez_processes():
    """Find all processes related to SharewareZ (uvicorn, python, etc.)"""
    processes = []
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'memory_info']):
        try:
            cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
            
            # Look for SharewareZ related processes
            if any([
                'uvicorn' in proc.info['name'],
                'asgi:asgi_app' in cmdline,
                'sharewarez' in cmdline.lower(),
                '/var/www/sharewarez' in cmdline,
                'modules' in cmdline and 'create_app' in cmdline
            ]):
                processes.append({
                    'pid': proc.info['pid'],
                    'name': proc.info['name'],
                    'cmdline': cmdline[:100] + '...' if len(cmdline) > 100 else cmdline,
                    'memory_rss': proc.info['memory_info'].rss if proc.info['memory_info'] else 0,
                    'memory_vms': proc.info['memory_info'].vms if proc.info['memory_info'] else 0
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    return processes

def format_bytes(bytes_value):
    """Convert bytes to human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.2f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.2f} TB"

def log_memory_usage(log_file, csv_file):
    """Log current memory usage to files"""
    timestamp = datetime.now()
    
    # Get system memory info
    memory = psutil.virtual_memory()
    swap = psutil.swap_memory()
    
    # Get SharewareZ processes
    processes = get_sharewarez_processes()
    
    # Calculate total memory usage by SharewareZ processes
    total_rss = sum(p['memory_rss'] for p in processes)
    total_vms = sum(p['memory_vms'] for p in processes)
    
    # Log to text file
    with open(log_file, 'a') as f:
        f.write(f"\n{'='*60}\n")
        f.write(f"Timestamp: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"System Memory - Total: {format_bytes(memory.total)}, "
                f"Used: {format_bytes(memory.used)} ({memory.percent}%), "
                f"Available: {format_bytes(memory.available)}\n")
        f.write(f"Swap Memory - Total: {format_bytes(swap.total)}, "
                f"Used: {format_bytes(swap.used)} ({swap.percent}%)\n")
        f.write(f"\nSharewareZ Processes ({len(processes)} found):\n")
        
        if processes:
            f.write(f"Total RSS Memory: {format_bytes(total_rss)}\n")
            f.write(f"Total VMS Memory: {format_bytes(total_vms)}\n")
            f.write(f"\nProcess Details:\n")
            for proc in processes:
                f.write(f"  PID {proc['pid']} ({proc['name']}): "
                        f"RSS {format_bytes(proc['memory_rss'])}, "
                        f"VMS {format_bytes(proc['memory_vms'])}\n")
                f.write(f"    CMD: {proc['cmdline']}\n")
        else:
            f.write("No SharewareZ processes found!\n")
    
    # Log to CSV file
    csv_exists = os.path.exists(csv_file)
    with open(csv_file, 'a', newline='') as f:
        writer = csv.writer(f)
        
        # Write header if file is new
        if not csv_exists:
            writer.writerow([
                'timestamp', 'system_memory_total_mb', 'system_memory_used_mb', 
                'system_memory_percent', 'system_memory_available_mb',
                'swap_total_mb', 'swap_used_mb', 'swap_percent',
                'sharewarez_processes_count', 'sharewarez_total_rss_mb', 
                'sharewarez_total_vms_mb', 'process_details'
            ])
        
        # Prepare process details for CSV
        process_details = '; '.join([
            f"PID{p['pid']}({p['name']}):{format_bytes(p['memory_rss'])}"
            for p in processes
        ]) if processes else "None"
        
        writer.writerow([
            timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            round(memory.total / (1024*1024), 2),
            round(memory.used / (1024*1024), 2),
            round(memory.percent, 2),
            round(memory.available / (1024*1024), 2),
            round(swap.total / (1024*1024), 2),
            round(swap.used / (1024*1024), 2),
            round(swap.percent, 2),
            len(processes),
            round(total_rss / (1024*1024), 2),
            round(total_vms / (1024*1024), 2),
            process_details
        ])

def main():
    parser = argparse.ArgumentParser(description='Monitor SharewareZ memory usage')
    parser.add_argument('--interval', type=int, default=5, 
                       help='Monitoring interval in seconds (default: 5)')
    parser.add_argument('--log-file', default='memory_monitor.log',
                       help='Log file path (default: memory_monitor.log)')
    parser.add_argument('--csv-file', default='memory_monitor.csv',
                       help='CSV file path (default: memory_monitor.csv)')
    parser.add_argument('--duration', type=int, 
                       help='Duration in minutes (default: run indefinitely)')
    
    args = parser.parse_args()
    
    log_file = os.path.abspath(args.log_file)
    csv_file = os.path.abspath(args.csv_file)
    
    print(f"SharewareZ Memory Monitor")
    print(f"Monitoring interval: {args.interval} seconds")
    print(f"Log file: {log_file}")
    print(f"CSV file: {csv_file}")
    if args.duration:
        print(f"Duration: {args.duration} minutes")
    print("Press Ctrl+C to stop monitoring")
    print("-" * 60)
    
    # Initialize log files
    with open(log_file, 'w') as f:
        f.write(f"SharewareZ Memory Monitor Started: {datetime.now()}\n")
        f.write(f"Monitoring interval: {args.interval} seconds\n")
    
    start_time = time.time()
    iterations = 0
    
    try:
        while True:
            log_memory_usage(log_file, csv_file)
            iterations += 1
            
            # Print progress to console
            elapsed = time.time() - start_time
            print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                  f"Logged iteration {iterations} "
                  f"(elapsed: {elapsed/60:.1f} min)")
            
            # Check duration limit
            if args.duration and elapsed >= args.duration * 60:
                print(f"\nReached duration limit of {args.duration} minutes. Stopping.")
                break
            
            time.sleep(args.interval)
            
    except KeyboardInterrupt:
        print(f"\nMonitoring stopped by user after {iterations} iterations")
        print(f"Total elapsed time: {(time.time() - start_time)/60:.1f} minutes")
        
    except Exception as e:
        print(f"Error during monitoring: {e}")
        sys.exit(1)
    
    print(f"\nLog files saved:")
    print(f"  Text log: {log_file}")
    print(f"  CSV log: {csv_file}")

if __name__ == "__main__":
    main()