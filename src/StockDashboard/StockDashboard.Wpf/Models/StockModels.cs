using System;
using System.Collections.Generic;
using System.Text.Json.Serialization;

namespace StockDashboard.Wpf.Models;

public sealed class StockDetailDto
{
    [JsonPropertyName("symbol")] public string Symbol { get; set; } = string.Empty;
    [JsonPropertyName("name")] public string? Name { get; set; }
    [JsonPropertyName("exchange")] public string? Exchange { get; set; }
    [JsonPropertyName("currency")] public string? Currency { get; set; }
    [JsonPropertyName("quote")] public QuoteDto Quote { get; set; } = new();
    [JsonPropertyName("metrics")] public MetricsDto Metrics { get; set; } = new();
    [JsonPropertyName("profile")] public ProfileDto Profile { get; set; } = new();
    [JsonPropertyName("chart")] public ChartDto Chart { get; set; } = new();
    [JsonPropertyName("fetched_at")] public DateTimeOffset FetchedAt { get; set; }
    [JsonPropertyName("source")] public string Source { get; set; } = "yfinance";
    [JsonPropertyName("disclaimer")] public string? Disclaimer { get; set; }
}

public sealed class QuoteDto
{
    [JsonPropertyName("price")] public double? Price { get; set; }
    [JsonPropertyName("previous_close")] public double? PreviousClose { get; set; }
    [JsonPropertyName("open")] public double? Open { get; set; }
    [JsonPropertyName("day_high")] public double? DayHigh { get; set; }
    [JsonPropertyName("day_low")] public double? DayLow { get; set; }
    [JsonPropertyName("volume")] public long? Volume { get; set; }
    [JsonPropertyName("change")] public double? Change { get; set; }
    [JsonPropertyName("change_percent")] public double? ChangePercent { get; set; }
}

public sealed class MetricsDto
{
    [JsonPropertyName("fifty_two_week_high")] public double? FiftyTwoWeekHigh { get; set; }
    [JsonPropertyName("fifty_two_week_low")] public double? FiftyTwoWeekLow { get; set; }
    [JsonPropertyName("market_cap")] public double? MarketCap { get; set; }
    [JsonPropertyName("pe_ratio")] public double? PeRatio { get; set; }
    [JsonPropertyName("eps")] public double? Eps { get; set; }
    [JsonPropertyName("dividend_yield")] public double? DividendYield { get; set; }
    [JsonPropertyName("beta")] public double? Beta { get; set; }
    [JsonPropertyName("average_volume")] public long? AverageVolume { get; set; }
}

public sealed class ProfileDto
{
    [JsonPropertyName("short_name")] public string? ShortName { get; set; }
    [JsonPropertyName("long_name")] public string? LongName { get; set; }
    [JsonPropertyName("sector")] public string? Sector { get; set; }
    [JsonPropertyName("industry")] public string? Industry { get; set; }
    [JsonPropertyName("summary")] public string? Summary { get; set; }
    [JsonPropertyName("website")] public string? Website { get; set; }
    [JsonPropertyName("country")] public string? Country { get; set; }
}

public sealed class ChartDto
{
    [JsonPropertyName("interval")] public string Interval { get; set; } = "1d";
    [JsonPropertyName("range")] public string Range { get; set; } = "6mo";
    [JsonPropertyName("points")] public List<ChartPointDto> Points { get; set; } = new();
}

public sealed class ChartPointDto
{
    [JsonPropertyName("date")] public string Date { get; set; } = string.Empty;
    [JsonPropertyName("open")] public double? Open { get; set; }
    [JsonPropertyName("high")] public double? High { get; set; }
    [JsonPropertyName("low")] public double? Low { get; set; }
    [JsonPropertyName("close")] public double? Close { get; set; }
    [JsonPropertyName("volume")] public long? Volume { get; set; }
}

public sealed class ApiErrorDto
{
    [JsonPropertyName("error_code")] public string ErrorCode { get; set; } = string.Empty;
    [JsonPropertyName("message")] public string Message { get; set; } = string.Empty;
    [JsonPropertyName("detail")] public string? Detail { get; set; }
}
