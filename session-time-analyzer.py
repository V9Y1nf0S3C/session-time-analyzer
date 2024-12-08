#!/usr/bin/env python3
import argparse
import re
import time
from datetime import datetime, timedelta
import requests
from colorama import init, Fore, Style
import os
from urllib.parse import urlparse
import logging
import httpx
import urllib3
import ssl
import json

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Initialize colorama for cross-platform color support
init()

def extract_and_write_token(response_text, token_file):
    """Extract token from response and write it to file"""
    token_pattern = r'"token":\s*"([^"]+)"'
    match = re.search(token_pattern, response_text)
    if match:
        token = match.group(1)
        with open(token_file, 'w') as f:
            f.write(token)
        return True
    return False
class GrepPattern:
    def __init__(self, pattern, is_regex, color, number):
        self.pattern = pattern
        self.is_regex = is_regex
        self.color = color  # Changed from is_green to color
        self.number = number

def parse_arguments():
    parser = argparse.ArgumentParser(description='HTTP Request Analyzer with Grep Features')
    parser.add_argument('--proxy', help='Proxy for the request')
    parser.add_argument('--init-sleep', type=int, default=0, help='Initial sleep time in minutes')
    parser.add_argument('--delay', type=int, default=5, help='Delay between requests in minutes')
    parser.add_argument('--increment-delay', type=int, default=2, help='Increment delay for each request in minutes')
    parser.add_argument('--grep-file', required=True, help='File containing grep patterns')
    parser.add_argument('--look-only-body', action='store_true', help='Look only in response body')
    parser.add_argument('--log-resp', help='File to log responses')
    parser.add_argument('--req-file', required=True, help='File containing the request')
    parser.add_argument('--case-sensitive-grep', action='store_true', help='Enable case sensitive grep')
    parser.add_argument('--max-requests', type=int, help='Maximum number of requests to send before exiting')
    parser.add_argument('--max-delay', type=int, help='Maximum allowed delay in minutes before exiting')
    parser.add_argument('--write-session-token', help='File to write the session token')
    return parser.parse_args()


def print_settings(args, start_time):
    print("\nScript Settings:")
    print("=" * 50)
    print(f"Start Time: {format_timestamp(start_time)}")
    print(f"Request File: {args.req_file}")
    print(f"Grep File: {args.grep_file}")
    print(f"Proxy: {args.proxy if args.proxy else 'Not configured'}")
    print(f"Initial Sleep: {args.init_sleep} minutes")
    print(f"Delay between requests: {args.delay} minutes")
    print(f"Delay increment: {args.increment_delay} minutes")
    print(f"Look only body: {args.look_only_body}")
    print(f"Case sensitive grep: {args.case_sensitive_grep}")
    print(f"Response logging: {'Enabled -> ' + args.log_resp if args.log_resp else 'Disabled'}")
    print(f"Max requests: {args.max_requests if args.max_requests else 'Unlimited'}")
    print(f"Max delay: {args.max_delay if args.max_delay else 'Unlimited'} minutes")
    print(f"Write session token: {'Enabled -> ' + args.write_session_token if args.write_session_token else 'Disabled'}")
    print("=" * 50)

def escape_pattern(pattern):
    """Escape special characters in the pattern."""
    #special_chars = ['/', '\\', '.', '^', '$', '*', '+', '?', '(', ')', '[', ']', '{', '}', '|']
    special_chars = ['\\'] # DEBUG
    for char in special_chars:
        pattern = pattern.replace(char, '\\' + char)
    return pattern


def parse_grep_file(grep_file):
    patterns = []
    current_section = None
    pattern_number = 1

    with open(grep_file, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('::'):  # Skip empty lines and comments
                continue
            
            if line.startswith('['):
                current_section = line.lower()
                continue
            
            is_regex = 'regex' in current_section
            # Determine color based on section
            if 'green' in current_section:
                color = 'green'
            elif 'yellow' in current_section:
                color = 'yellow'
            else:
                color = 'red'
            
            # Escape special characters if it's not a regex pattern
            pattern = line if is_regex else escape_pattern(line)
            patterns.append(GrepPattern(pattern, is_regex, color, pattern_number))
            pattern_number += 1
            
    return patterns

def parse_request_file(req_file):
    with open(req_file, 'r') as f:
        lines = f.readlines()

    # Parse first line for method, path and HTTP version
    first_line = lines[0].strip().split()
    method = first_line[0]
    path = first_line[1]
    http_version = first_line[2] if len(first_line) > 2 else 'HTTP/1.1'
    # print(f"DEBUG: http_version: {http_version}")
    
    # Parse headers
    headers = {}
    body = None
    reading_body = False
    body_lines = []
    
    for line in lines[1:]:
        if reading_body:
            body_lines.append(line)
        elif line.strip() == "":
            reading_body = True
        else:
            if ":" in line:
                key, value = line.split(":", 1)
                headers[key.strip()] = value.strip()
    
    if body_lines:
        body = "".join(body_lines)

    # Extract host from headers
    host = headers.get('Host', '')
    url = f"https://{host}{path}"
    
    return {
        'method': method,
        'url': url,
        'headers': headers,
        'body': body,
        'http_version': http_version
    }

def check_pattern(pattern, text, case_sensitive):
    if not case_sensitive:
        text = text.lower()
        pattern_text = pattern.pattern.lower()
    else:
        pattern_text = pattern.pattern

    if pattern.is_regex:
        try:
            #print(f"DEBUG: pattern_text: {pattern_text}")
            return bool(re.search(pattern_text, text, re.MULTILINE)) #DEBUG re.MULTILINE added
        except re.error:
            print(f"Invalid regex pattern: {pattern_text}")
            return False
    else:
        # print(f"Debug: Checking for {pattern_text}")
        return pattern_text in text

def format_timestamp(dt):
    return dt.strftime('%Y.%d.%m-%H:%M:%S')

def print_legend(patterns):
    print("\nLegend:")
    for pattern in patterns:
        color = Fore.GREEN if pattern.color == 'green' else Fore.YELLOW if pattern.color == 'yellow' else Fore.RED
        pattern_type = f"[regex-grep-{pattern.color}]" if pattern.is_regex else f"[normal-grep-{pattern.color}]"
        print(f"{pattern.number:2d}.{pattern_type} {pattern.pattern}")
    print(Style.RESET_ALL)

def print_request_line(req_file):
    with open(req_file, 'r') as f:
        first_line = f.readline().strip()
    print(f"\nRequest: {first_line}")
def print_table_header(patterns):
    # Calculate widths
    sno_width = 5       # Width for S.No (####)
    timestamp_width = 19  # YYYY.DD.MM-HH:MM:SS
    delay_width = 8      # Width for delay column (MM:SS)
    pattern_width = 3    # Width for pattern columns
    
    # Create header parts
    time_header = f"{' S.No':^{sno_width}} | {'Current Time':^{timestamp_width}} | {'Delay':^{delay_width}} | {'Next Request Time':^{timestamp_width}}"
    
    # Create pattern number headers
    pattern_headers = []
    for p in patterns:
        pattern_headers.append(f"{p.number}")
    
    # Calculate total width
    total_width = len(time_header) + 3 + (len(patterns) * 4)
    
    print("-" * total_width)
    print(f"{time_header} ", end="")
    for header in pattern_headers:
        print(f"|{header:^3}", end="")
    print("|")
    print("-" * total_width)
    
    return sno_width, timestamp_width, delay_width, pattern_width

def format_delay(time_diff):
    """Format timedelta as MM:SS"""
    total_seconds = int(time_diff.total_seconds())
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes:02d}:{seconds:02d}"
    
    

def format_table_row(sno, current_time, next_time, results, sno_width, timestamp_width, delay_width, pattern_width):
    time_diff = next_time - current_time
    delay_str = format_delay(time_diff)
    
    row = f"{sno:>{sno_width}} | {format_timestamp(current_time):<{timestamp_width}} | {delay_str:^{delay_width}} | {format_timestamp(next_time):<{timestamp_width}} |"
    
    for result in results:
        row += f" {result} |"  # Changed from f"{result:^4}|" to f" {result} |"
    
    return row

def get_pattern_symbol(match, color):
    """Get the appropriate symbol and color for pattern match"""
    if not match:
        return ' '  # Changed from '   ' to ' ' - single space for no match
    
    if color == 'green':
        return f"{Fore.GREEN}+{Style.RESET_ALL}"
    elif color == 'yellow':
        return f"{Fore.YELLOW}?{Style.RESET_ALL}"
    else:  # red
        return f"{Fore.RED}X{Style.RESET_ALL}"

def get_headers_as_text(response):
    """Convert headers to a readable text format"""
    headers_text = []
    if isinstance(response, httpx.Response):
        # For httpx response
        for name, value in response.headers.items():
            headers_text.append(f"{name}: {value}")
    else:
        # For requests response
        for name, value in response.headers.items():
            headers_text.append(f"{name}: {value}")
    
    return "\n".join(headers_text)
    
def get_response_text(response, look_only_body=False):
    if look_only_body:
        return response.text
    
    # Get status line directly from response
    if isinstance(response, httpx.Response):
        #status_line = f"HTTP/{response.http_version} {response.status_code} {response.reason_phrase}"
        status_line = f"{response.http_version} {response.status_code} {response.reason_phrase}"
    else:
        #print(f"DEBUG: ------- WRONG ---------  {response.status_code} {response.reason}")
        status_line = f"HTTP/1.1 {response.status_code} {response.reason}"
    
    headers_text = get_headers_as_text(response)
    #print(f"DEBUG: status_line: {status_line}  \nheaders_text: {headers_text}\n\nresponse.text: {response.text}")
    return f"{status_line}\n{headers_text}\n\n{response.text}"

def main():
    args = parse_arguments()
    start_time = datetime.now()
    
    # Print settings
    print_settings(args, start_time)
    
    patterns = parse_grep_file(args.grep_file)
    request_data = parse_request_file(args.req_file)
    
    #print(f"DEBUG: Before - request_data: {request_data}")
    # Remove "Connection: keep-alive" if not present in input file
    if 'Connection' not in request_data['headers']:
        request_data['headers'].pop('Connection', None)
    #print(f"DEBUG: Before - request_data: {request_data}")
    
    if args.log_resp:
        logging.basicConfig(filename=args.log_resp, level=logging.INFO)
    
    # Print legend
    print_legend(patterns)
    # timestamp_width, delay_width, pattern_width = print_table_header(patterns)
    
    # Print request line
    print_request_line(args.req_file)
    
    # Get all widths once
    sno_width, timestamp_width, delay_width, pattern_width = print_table_header(patterns)
    
    if args.init_sleep > 0:
        time.sleep(args.init_sleep * 60)
    
    current_delay = args.delay
    # Initialize request counter
    request_counter = 1
    
    # Configure client based on HTTP version
    is_http2 = False #request_data['http_version'].upper() == 'HTTP/2'
    
    while True:
        try:
            current_time = datetime.now()
            next_request_time = current_time + timedelta(minutes=current_delay)

                                
            # print(f"DEBUG: is_http2:{is_http2}\n")
            # Send request using appropriate HTTP version
            if is_http2:
                transport = httpx.HTTPTransport(verify=False) #,http1=False)
                
                if args.proxy:
                    transport = httpx.HTTPTransport(
                        verify=False,
                        proxy=httpx.Proxy(args.proxy)
                    )
                
                with httpx.Client(transport=transport, http2=True) as client:
                    response = client.request(
                        method=request_data['method'],
                        url=request_data['url'],
                        headers=request_data['headers'],
                        content=request_data['body']
                    )
                # print(f"DEBUG - Protocol used H: {response.http_version}\n")  # For httpx
            else:
                response = requests.request(
                    method=request_data['method'],
                    url=request_data['url'],
                    headers=request_data['headers'],
                    data=request_data['body'],
                    proxies={'http': args.proxy, 'https': args.proxy} if args.proxy else None,
                    verify=False  # Disable SSL verification for proxy
                )
                # print(f"DEBUG - Protocol used R: {response.raw.version}\n")  # For requests

            
            #print(f"DEBUG: request_data[]:{request_data}  \nrequest_data['method']:{request_data['method']}  \nrequest_data['url']:{request_data['url']}  \nrequest_data['headers']:{request_data['headers']}  \nrequest_data['body']:{request_data['body']}")

            #print(f"DEBUG: response:{response}\n")
            # Get complete response text
            search_text = get_response_text(response, args.look_only_body)
            
            #print(f"DEBUG: search_text:{search_text}\n")
            # Log response if requested
            # Extract and write token if enabled
            if args.write_session_token:
                if extract_and_write_token(search_text, args.write_session_token):
                    #print(f"Session token extracted and written to {args.write_session_token}")
                    if args.log_resp:
                        logging.info(f"\nSession token extracted and written to {args.write_session_token}")
            
            if args.log_resp:
                logging.info(f"\n{'='*50}\n{format_timestamp(current_time)}\n{search_text}\n{'='*50}")
            
            # Check patterns and format results
            results = []
            for pattern in patterns:
                match = check_pattern(pattern, search_text, args.case_sensitive_grep)
                symbol = get_pattern_symbol(match, pattern.color)
                results.append(symbol)
                
            
            # Print results
            print(format_table_row(request_counter, current_time, next_request_time, results, 
                                 sno_width, timestamp_width, delay_width, pattern_width))
            
            request_counter += 1

            # Check max requests limit
            if args.max_requests and request_counter > args.max_requests:
                print(f"\n{format_timestamp(current_time)}: Reached maximum requests limit ({args.max_requests}). Exiting...")
                break

            # Check max delay limit
            if args.max_delay:
                delay_minutes = (next_request_time - current_time).total_seconds() / 60
                if delay_minutes > args.max_delay:
                    print(f"\n{format_timestamp(current_time)}: Next delay ({delay_minutes:.1f} minutes) would exceed maximum delay limit ({args.max_delay} minutes). Exiting...")
                    break            
            
            # Wait and increment delay
            time.sleep(current_delay * 60)
            current_delay += args.increment_delay
            
        except Exception as e:
            print(f"Error: {str(e)}")
            time.sleep(current_delay * 60)
            continue

if __name__ == "__main__":
    main()
