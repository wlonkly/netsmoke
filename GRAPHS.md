# SmokePing Graph Visualization Guide

This document explains how to create SmokePing-style "smoke" graphs that visualize the distribution of network latency measurements.

## What is the Smoke Effect?

The "smoke" effect is SmokePing's signature visualization technique that shows the distribution of multiple ping samples at each measurement interval. Instead of just plotting a single median line, it displays the full range of latencies using stacked grayscale bands:

- **Lighter gray** = rare outliers (min/max values)
- **Darker gray** = common variance (values closer to median)
- **Median line/dots** = the median latency trend

This allows you to see at a glance:

- Latency trends over time
- Network stability (narrow smoke = consistent, wide smoke = high variance)
- Outliers and their frequency

## How SmokePing Implements It

### Data Storage

SmokePing stores each individual ping sample as a separate data source in RRD files:

- `ping1`, `ping2`, `ping3`, ..., `ping20` (if doing 20 pings per measurement)
- Plus `median` and `loss` aggregates

This is unusual - most time-series systems only store aggregates (min/max/avg). But storing individual samples is **essential** for the smoke effect.

### The Algorithm (from `SmokePing/lib/Smokeping.pm:1086-1100`)

```perl
sub smokecol ($) {
    my $count = shift;  # number of pings (e.g., 20)
    return [] unless $count > 2;
    my $half = $count/2;
    my @items;
    my $itop=$count;
    my $ibot=1;
    for (; $itop > $ibot; $itop--,$ibot++){
        # Calculate grayscale: darker at extremes, lighter in middle
        my $color = int(190/$half * ($half-$ibot))+50;

        # Create CDEF for the band height (difference between top and bottom)
        push @items, "CDEF:smoke${ibot}=cp${ibot},UN,UNKN,cp${itop},cp${ibot},-,IF";

        # Draw base area (bottom ping)
        push @items, "AREA:cp${ibot}";

        # Stack the difference on top with grayscale color
        push @items, "STACK:smoke${ibot}#".(sprintf("%02x",$color) x 3);
    };
    return \@items;
}
```

### Key Insights

1. **Pair pings from outside-in**: The algorithm pairs the minimum ping with the maximum, second-minimum with second-maximum, etc.

2. **Color calculation**: `gray_value = int(190/half * (half-ibot)) + 50`
   - This produces values from 50 (darker) to 240 (lighter)
   - Lighter colors for extreme pairs (rare outliers), darker for middle pairs (common variance near median)

3. **Stacking technique**:
   - Draw invisible `AREA` from 0 to bottom ping value
   - `STACK` the difference (top - bottom) on top of it
   - This creates a band between the two ping values

4. **RRDtool commands used**:
   - `DEF:` - Load data from RRD file
   - `CDEF:` - Calculate derived values
   - `AREA:` - Draw area from 0 to value
   - `STACK:` - Stack area on top of previous area

## Implementing in Modern Tools

### Requirements

Any graphing library that supports:

- Stacked bar charts (or stacked area charts)
- Custom colors per series
- Overlay of scatter plot or line on top

### Python + matplotlib Implementation

See `smoke_poc_bars.py` for full working example.

#### Step 1: Store All Ping Samples

```python
# Each row contains all N ping samples for that timestamp
pings_data = np.array([
    [ping1, ping2, ..., ping20],  # timestamp 1
    [ping1, ping2, ..., ping20],  # timestamp 2
    # ...
])
```

#### Step 2: Calculate Smoke Bands

```python
def calculate_smoke_bands(pings_data):
    num_timestamps, num_pings = pings_data.shape

    # Sort pings at each timestamp
    sorted_pings = np.sort(pings_data, axis=1)

    bands = []
    half = num_pings // 2

    # Pair from outside-in
    for ibot in range(half):
        itop = num_pings - 1 - ibot

        # Calculate grayscale (matching SmokePing's formula)
        gray_value = int(190 / half * (half - ibot)) + 50
        color = f'#{gray_value:02x}{gray_value:02x}{gray_value:02x}'

        bands.append({
            'bottom': sorted_pings[:, ibot],
            'height': sorted_pings[:, itop] - sorted_pings[:, ibot],
            'color': color
        })

    return bands
```

#### Step 3: Render with Stacked Bars

```python
def plot_smoke_graph(timestamps, pings_data):
    fig, ax = plt.subplots(figsize=(12, 6))

    # Calculate median
    median = np.median(pings_data, axis=1)

    # Get smoke bands
    bands = calculate_smoke_bands(pings_data)

    # Calculate bar width (make bars touch)
    x = date2num(timestamps)
    width = np.min(np.diff(x)) if len(x) > 1 else 1.0/24.0

    # Draw each band as stacked bars
    for band in bands:
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

    # Overlay median as scatter plot
    ax.scatter(timestamps, median, color='#00ff00', s=20,
               label='Median RTT', zorder=100, linewidths=0)

    # Formatting
    ax.set_xlabel('Time')
    ax.set_ylabel('Latency (ms)')
    ax.set_title('Ping Latency with Smoke Effect')
    ax.grid(True, alpha=0.3, linestyle='--', zorder=0)
    ax.set_ylim(bottom=0)

    return fig
```

### Other Libraries

**Plotly (Python/JavaScript)**:

- Use `go.Bar()` with `base` parameter for stacking
- Same algorithm, different API

**D3.js**:

- Use `d3.area()` with custom y0/y1 accessors
- Full control over rendering

**Apache ECharts**:

- Use stacked bar series
- Configure `areaStyle` and `stack` properties

## Visual Comparison: Area vs Bars

**Original SmokePing**: Uses area charts that create smooth, flowing smoke

**Our POC**: Uses stacked bars that create columnar smoke

- Bars better show individual measurement intervals
- Easier to implement with most charting libraries
- Still conveys the same information effectively

Both approaches work - choose based on your aesthetic preference and library capabilities.

## Database Considerations

To enable smoke graphs, you **must store individual ping samples**, not just aggregates.

### Recommended Schema (PostgreSQL + TimescaleDB)

```sql
CREATE TABLE ping_samples (
    time        TIMESTAMPTZ NOT NULL,
    target      TEXT NOT NULL,
    sample_num  SMALLINT NOT NULL,  -- 1 to N (e.g., 20)
    rtt_ms      REAL,               -- NULL = packet loss
    PRIMARY KEY (time, target, sample_num)
);

SELECT create_hypertable('ping_samples', 'time');
```

### Query for Graphing

```sql
-- Get all samples for a time range
SELECT time, sample_num, rtt_ms
FROM ping_samples
WHERE target = 'google.com'
  AND time > NOW() - INTERVAL '8 hours'
ORDER BY time, sample_num;
```

Then pivot this data into the 2D array format for graphing:

- Rows = timestamps
- Columns = sample numbers
- Values = RTT in ms

## Performance Considerations

**Storage**: 20 samples × 1 measurement/min = 28,800 samples/day per target

- With compression (TimescaleDB): ~400MB/day for 100 targets
- RRDtool's fixed-size files were designed for this use case

**Rendering**:

- 100 timestamps × 10 smoke bands = 1,000 bar segments
- Easily handled by matplotlib, Plotly, etc.
- Consider reducing resolution for very long time ranges

## References

- Original SmokePing code: `SmokePing/lib/Smokeping.pm` (smokecol function)
- Multi-host graphs: `SmokePing/lib/Smokeping/Graphs.pm` (get_multi_detail function)
- Proof of concept: `smoke_poc_bars.py`
- Example output: `smoke_poc_bars_output.png`

## Example Output

The POC generates graphs showing:

- 8 hours of synthetic ping data
- 100 measurement intervals
- 20 pings per interval
- Smoke bands showing distribution
- Green dots showing median trend

The result clearly shows:

- Baseline latency periods (narrow, consistent smoke)
- Congestion events (wide smoke, high median)
- Outliers (light wisps extending from main smoke)

---

**Key Takeaway**: The smoke effect is just clever use of stacked charts with paired min/max samples and graduated grayscale colors. It's completely portable to any modern graphing library.
