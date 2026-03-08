#!/usr/bin/env python3
"""
Proof of concept: SmokePing-style smoke graph using matplotlib with BARS

This version uses stacked bars to create the columnar effect that
SmokePing's graphs have, rather than smooth area fills.
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.dates import date2num
from datetime import datetime, timedelta


def generate_synthetic_pings(num_timestamps=100, num_pings=20):
    """
    Generate synthetic ping data that simulates real network behavior.

    Returns:
        timestamps: list of datetime objects
        pings_data: 2D array of shape (num_timestamps, num_pings)
                    Each row contains num_pings samples for that timestamp
    """
    # Create timestamps (e.g., every 5 minutes)
    start_time = datetime.now() - timedelta(hours=8)
    timestamps = [start_time + timedelta(minutes=5*i) for i in range(num_timestamps)]

    # Generate realistic ping data
    pings_data = []
    base_latency = 50.0  # ms

    for i in range(num_timestamps):
        # Add a slow trend (day/night variations)
        trend = 10 * np.sin(i / num_timestamps * 2 * np.pi)

        # Add occasional congestion spikes
        if np.random.random() < 0.1:  # 10% chance of congestion
            spike = np.random.uniform(20, 80)
        else:
            spike = 0

        # Generate individual pings with normal distribution
        mean_latency = base_latency + trend + spike
        stddev = 5.0 + spike * 0.2  # More variance during spikes

        pings = np.random.normal(mean_latency, stddev, num_pings)
        pings = np.maximum(pings, 1.0)  # No negative latencies

        pings_data.append(pings)

    return timestamps, np.array(pings_data)


def calculate_smoke_bands(pings_data):
    """
    Calculate the smoke bands using SmokePing's algorithm.

    Returns:
        bands: list of dicts, each containing:
               - 'bottom': array of bottom values
               - 'height': array of height values (for stacking)
               - 'color': RGB color tuple
    """
    num_timestamps, num_pings = pings_data.shape

    # Sort pings at each timestamp
    sorted_pings = np.sort(pings_data, axis=1)

    # Calculate bands (pair outside-in)
    bands = []
    half = num_pings // 2

    for ibot in range(half):
        itop = num_pings - 1 - ibot

        # Calculate grayscale color (darker at extremes, lighter in middle)
        gray_value = int(190 / half * (half - ibot)) + 50
        color = f'#{gray_value:02x}{gray_value:02x}{gray_value:02x}'

        # For stacked bars, we need the bottom position and height
        bottom = sorted_pings[:, ibot]
        height = sorted_pings[:, itop] - sorted_pings[:, ibot]

        bands.append({
            'bottom': bottom,
            'height': height,
            'color': color
        })

    return bands


def plot_smoke_graph_bars(timestamps, pings_data, title="Ping Latency with Smoke Effect (Bars)"):
    """
    Create a SmokePing-style graph with matplotlib using stacked bars.
    """
    # Calculate median for the line
    median = np.median(pings_data, axis=1)

    # Calculate smoke bands
    bands = calculate_smoke_bands(pings_data)

    # Create the plot
    fig, ax = plt.subplots(figsize=(12, 6))

    # Convert timestamps to numbers for bar width calculation
    x = date2num(timestamps)

    # Calculate bar width (make bars touch each other with no gap)
    if len(x) > 1:
        # Width is the difference between timestamps
        width = np.min(np.diff(x))
    else:
        width = 1.0 / 24.0  # Default to 1 hour if only one point

    # Draw smoke bands as stacked bars
    # Start from the first band (darkest, outermost) and stack upward
    cumulative_bottom = None

    for i, band in enumerate(bands):
        if i == 0:
            # First band: draw from 0 to bottom, then stack the height
            # Actually, for the effect we want, we draw from bottom with height
            ax.bar(
                x,
                band['height'],
                width=width,
                bottom=band['bottom'],
                color=band['color'],
                linewidth=0,
                align='center',
                edgecolor='none'
            )
        else:
            # Subsequent bands stack on top
            ax.bar(
                x,
                band['height'],
                width=width,
                bottom=band['bottom'],
                color=band['color'],
                linewidth=0,
                align='center',
                edgecolor='none'
            )

    # Draw median as scatter plot on top
    ax.scatter(timestamps, median, color='#00ff00', s=20, label='Median RTT', zorder=100, linewidths=0)

    # Formatting
    ax.set_xlabel('Time')
    ax.set_ylabel('Latency (ms)')
    ax.set_title(title)
    ax.grid(True, alpha=0.3, linestyle='--', zorder=0)
    ax.legend()

    # Format x-axis to show times nicely
    fig.autofmt_xdate()

    # Set y-axis to start at 0
    ax.set_ylim(bottom=0)

    plt.tight_layout()
    return fig


def print_statistics(pings_data):
    """Print some statistics about the ping data."""
    print("Ping Statistics:")
    print(f"  Number of timestamps: {pings_data.shape[0]}")
    print(f"  Pings per timestamp: {pings_data.shape[1]}")
    print(f"  Overall median: {np.median(pings_data):.2f} ms")
    print(f"  Overall mean: {np.mean(pings_data):.2f} ms")
    print(f"  Overall std dev: {np.std(pings_data):.2f} ms")
    print(f"  Min: {np.min(pings_data):.2f} ms")
    print(f"  Max: {np.max(pings_data):.2f} ms")
    print()


if __name__ == '__main__':
    # Generate synthetic data
    print("Generating synthetic ping data...")
    timestamps, pings_data = generate_synthetic_pings(num_timestamps=100, num_pings=20)

    print_statistics(pings_data)

    # Create the smoke graph with bars
    print("Creating smoke graph with bars...")
    fig = plot_smoke_graph_bars(timestamps, pings_data)

    # Save to file
    output_file = 'smoke_poc_bars_output.png'
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"Graph saved to: {output_file}")

    # Show the plot
    plt.show()

    print("\nThe 'smoke' columns show the distribution of ping times:")
    print("  - Darker gray = rare outliers (min/max)")
    print("  - Lighter gray = common variance (closer to median)")
    print("  - Green dots = median latency")
    print("  - Each vertical bar represents one measurement interval")
