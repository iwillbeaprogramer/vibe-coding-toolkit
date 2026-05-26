using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Net.Http;
using System.Net.Http.Json;
using System.Text.Json.Serialization;
using System.Threading;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Shapes;
using System.Windows.Threading;

namespace stock_dashboard
{
    public partial class MainWindow : Window
    {
        // 백엔드 주소는 코드 상수로 분리한다. 향후 설정 파일 분리 여지를 남긴다.
        private const string ApiBaseUrl = "http://127.0.0.1:8000";
        private static readonly TimeSpan HttpTimeout = TimeSpan.FromSeconds(15);
        // 리사이즈 이벤트가 폭주할 때 마지막 한 번만 렌더링하기 위한 지연 시간.
        private static readonly TimeSpan ResizeDebounce = TimeSpan.FromMilliseconds(30);

        private readonly HttpClient httpClient;
        private bool isLoading;
        private string currentRange = "1mo";
        private string? lastSymbol;
        private double[]? lastClosePrices;
        private DispatcherTimer? resizeDebounceTimer;

        // 테마 브러시는 한 번만 해석해 둔다. 키 누락 시 안전한 폴백을 사용한다.
        private Brush brushAccent = Brushes.DeepSkyBlue;
        private Brush brushPositive = Brushes.LimeGreen;
        private Brush brushNegative = Brushes.Crimson;
        private Brush brushWarning = Brushes.Orange;
        private Brush brushTextSecondary = Brushes.Gray;
        private Brush brushChartFill = Brushes.Transparent;

        public MainWindow()
        {
            InitializeComponent();
            httpClient = new HttpClient { BaseAddress = new Uri(ApiBaseUrl), Timeout = HttpTimeout };
            cacheThemeBrushes();
            Closed += onWindowClosed;
            SymbolTextBox.Focus();
        }

        private void cacheThemeBrushes()
        {
            brushAccent = resolveBrush("BrushAccent", brushAccent);
            brushPositive = resolveBrush("BrushPositive", brushPositive);
            brushNegative = resolveBrush("BrushNegative", brushNegative);
            brushWarning = resolveBrush("BrushWarning", brushWarning);
            brushTextSecondary = resolveBrush("BrushTextSecondary", brushTextSecondary);
            brushChartFill = resolveBrush("BrushChartFill", brushChartFill);
        }

        private Brush resolveBrush(string key, Brush fallback)
        {
            return TryFindResource(key) as Brush ?? fallback;
        }

        private void onWindowClosed(object? sender, EventArgs e)
        {
            if (resizeDebounceTimer != null)
            {
                resizeDebounceTimer.Stop();
                resizeDebounceTimer.Tick -= onResizeDebounceTick;
                resizeDebounceTimer = null;
            }
            httpClient.Dispose();
        }

        private async void OnSearchButtonClick(object sender, RoutedEventArgs e)
        {
            await runSearchAsync();
        }

        private async void OnSymbolTextBoxKeyDown(object sender, KeyEventArgs e)
        {
            if (e.Key == Key.Enter)
            {
                e.Handled = true;
                await runSearchAsync();
            }
        }

        private async void OnRangeChanged(object sender, SelectionChangedEventArgs e)
        {
            if (!IsLoaded) return;
            if (RangeComboBox.SelectedItem is ComboBoxItem item && item.Content is string content)
            {
                currentRange = content;
                if (!string.IsNullOrEmpty(lastSymbol) && !isLoading)
                {
                    await loadHistoryAsync(lastSymbol!);
                }
            }
        }

        private void OnChartCanvasSizeChanged(object sender, SizeChangedEventArgs e)
        {
            if (lastClosePrices == null || lastClosePrices.Length < 2) return;

            // 연속 리사이즈로 인한 가비지 누적과 프레임 드랍을 막기 위해 디바운스한다.
            if (resizeDebounceTimer == null)
            {
                resizeDebounceTimer = new DispatcherTimer { Interval = ResizeDebounce };
                resizeDebounceTimer.Tick += onResizeDebounceTick;
            }
            resizeDebounceTimer.Stop();
            resizeDebounceTimer.Start();
        }

        private void onResizeDebounceTick(object? sender, EventArgs e)
        {
            resizeDebounceTimer?.Stop();
            if (lastClosePrices != null && lastClosePrices.Length > 1)
            {
                renderChart(lastClosePrices);
            }
        }

        private async Task runSearchAsync()
        {
            if (isLoading) return;

            var rawSymbol = SymbolTextBox.Text ?? string.Empty;
            var normalized = rawSymbol.Trim().ToUpperInvariant();
            if (string.IsNullOrEmpty(normalized))
            {
                showStatus("티커를 입력하세요.", StatusKind.Warning);
                return;
            }
            if (!isValidSymbolFormat(normalized))
            {
                showStatus("티커는 영문/숫자/.,- 만 사용할 수 있습니다.", StatusKind.Warning);
                return;
            }

            setLoading(true);
            showStatus($"{normalized} 정보를 불러오는 중...", StatusKind.Info);

            try
            {
                var summary = await fetchSummaryAsync(normalized);
                renderSummary(summary);
                lastSymbol = normalized;

                await loadHistoryAsync(normalized);
                showStatus($"{normalized} 정보를 불러왔습니다.", StatusKind.Success);
            }
            catch (StockApiException apiEx)
            {
                showStatus(apiEx.Message, StatusKind.Error);
            }
            catch (TaskCanceledException)
            {
                showStatus("요청 시간이 초과되었습니다. 네트워크 또는 백엔드를 확인하세요.", StatusKind.Error);
            }
            catch (HttpRequestException httpEx)
            {
                showStatus($"백엔드({ApiBaseUrl})에 연결할 수 없습니다. 서버를 실행했는지 확인하세요. ({httpEx.Message})", StatusKind.Error);
            }
            catch (Exception ex)
            {
                showStatus($"알 수 없는 오류가 발생했습니다: {ex.Message}", StatusKind.Error);
            }
            finally
            {
                setLoading(false);
                // 연속 검색을 위해 입력란으로 포커스를 되돌리고 기존 텍스트를 선택해 둔다.
                SymbolTextBox.Focus();
                SymbolTextBox.SelectAll();
            }
        }

        private async Task loadHistoryAsync(string symbol)
        {
            try
            {
                var history = await fetchHistoryAsync(symbol, currentRange, "1d");
                var closes = history.Prices
                    .Where(p => p.Close.HasValue)
                    .Select(p => p.Close!.Value)
                    .ToArray();
                lastClosePrices = closes;
                ChartRangeLabel.Text = $"{symbol} · {history.Range} · {history.Interval} · {closes.Length}개 데이터";
                renderChart(closes);
            }
            catch (StockApiException apiEx)
            {
                showStatus($"차트 데이터를 가져오지 못했습니다: {apiEx.Message}", StatusKind.Error);
                clearChart();
            }
        }

        private async Task<StockSummary> fetchSummaryAsync(string symbol)
        {
            using var cts = new CancellationTokenSource(HttpTimeout);
            var response = await httpClient.GetAsync($"/api/stocks/{symbol}/summary", cts.Token);
            await ensureSuccessAsync(response);
            var summary = await response.Content.ReadFromJsonAsync<StockSummary>(cancellationToken: cts.Token);
            if (summary == null)
            {
                throw new StockApiException("요약 응답 본문이 비어 있습니다.");
            }
            return summary;
        }

        private async Task<StockHistory> fetchHistoryAsync(string symbol, string range, string interval)
        {
            using var cts = new CancellationTokenSource(HttpTimeout);
            var path = $"/api/stocks/{symbol}/history?range={Uri.EscapeDataString(range)}&interval={Uri.EscapeDataString(interval)}";
            var response = await httpClient.GetAsync(path, cts.Token);
            await ensureSuccessAsync(response);
            var history = await response.Content.ReadFromJsonAsync<StockHistory>(cancellationToken: cts.Token);
            if (history == null)
            {
                throw new StockApiException("차트 응답 본문이 비어 있습니다.");
            }
            return history;
        }

        private static async Task ensureSuccessAsync(HttpResponseMessage response)
        {
            if (response.IsSuccessStatusCode) return;
            string message;
            try
            {
                var error = await response.Content.ReadFromJsonAsync<ApiErrorEnvelope>();
                message = error?.Error?.Message ?? $"HTTP {(int)response.StatusCode} {response.ReasonPhrase}";
            }
            catch
            {
                message = $"HTTP {(int)response.StatusCode} {response.ReasonPhrase}";
            }

            if ((int)response.StatusCode == 404)
            {
                throw new StockApiException($"종목 데이터를 찾을 수 없습니다. ({message})");
            }
            if ((int)response.StatusCode >= 500)
            {
                throw new StockApiException($"백엔드 또는 데이터 공급원 오류: {message}");
            }
            throw new StockApiException(message);
        }

        private void renderSummary(StockSummary summary)
        {
            SymbolLabel.Text = summary.Symbol ?? "—";
            NameLabel.Text = string.IsNullOrWhiteSpace(summary.Name) ? (summary.Symbol ?? "—") : summary.Name!;
            ExchangeLabel.Text = combineParts(summary.Exchange, summary.QuoteType);

            PriceLabel.Text = formatMoney(summary.Price, summary.Currency);
            applyChange(summary.Change, summary.ChangePercent);

            PrevCloseLabel.Text = formatMoney(summary.PrevClose, summary.Currency);
            OpenLabel.Text = formatMoney(summary.Open, summary.Currency);
            HighLabel.Text = formatMoney(summary.High, summary.Currency);
            LowLabel.Text = formatMoney(summary.Low, summary.Currency);
            VolumeLabel.Text = formatInteger(summary.Volume);
            AvgVolumeLabel.Text = formatInteger(summary.AverageVolume);
            MarketCapLabel.Text = formatCompactCurrency(summary.MarketCap, summary.Currency);
            CurrencyLabel.Text = summary.Currency ?? "—";
            FiftyTwoHighLabel.Text = formatMoney(summary.FiftyTwoWeekHigh, summary.Currency);
            FiftyTwoLowLabel.Text = formatMoney(summary.FiftyTwoWeekLow, summary.Currency);
            SectorLabel.Text = string.IsNullOrWhiteSpace(summary.Sector) ? "—" : summary.Sector!;
            IndustryLabel.Text = string.IsNullOrWhiteSpace(summary.Industry) ? "—" : summary.Industry!;
        }

        private void applyChange(double? change, double? changePercent)
        {
            if (change == null && changePercent == null)
            {
                ChangeLabel.Text = "—";
                ChangePercentLabel.Text = "";
                ChangeLabel.Foreground = brushTextSecondary;
                ChangePercentLabel.Foreground = brushTextSecondary;
                return;
            }

            var isPositive = (change ?? 0) >= 0;
            var brush = isPositive ? brushPositive : brushNegative;
            ChangeLabel.Foreground = brush;
            ChangePercentLabel.Foreground = brush;

            var sign = isPositive ? "+" : "";
            ChangeLabel.Text = change.HasValue
                ? $"{sign}{change.Value.ToString("F2", CultureInfo.InvariantCulture)}"
                : "—";
            ChangePercentLabel.Text = changePercent.HasValue
                ? $"({sign}{changePercent.Value.ToString("F2", CultureInfo.InvariantCulture)}%)"
                : "";
        }

        private void renderChart(double[] closes)
        {
            ChartCanvas.Children.Clear();
            if (closes == null || closes.Length < 2)
            {
                ChartPlaceholderLabel.Text = "차트를 그릴 데이터가 부족합니다.";
                ChartPlaceholderLabel.Visibility = Visibility.Visible;
                return;
            }

            var width = ChartCanvas.ActualWidth;
            var height = ChartCanvas.ActualHeight;
            if (width <= 1 || height <= 1) return;

            ChartPlaceholderLabel.Visibility = Visibility.Collapsed;

            const double padding = 18.0;
            var minValue = closes.Min();
            var maxValue = closes.Max();
            var range = maxValue - minValue;
            // 모든 가격이 동일하면 수평선을 캔버스 중앙에 그려 가시성을 확보한다.
            var hasRange = range > 0;

            var innerWidth = Math.Max(1.0, width - padding * 2);
            var innerHeight = Math.Max(1.0, height - padding * 2);
            var midY = padding + innerHeight / 2.0;

            var points = new PointCollection();
            for (int i = 0; i < closes.Length; i++)
            {
                var x = padding + innerWidth * i / (closes.Length - 1);
                var y = hasRange
                    ? padding + innerHeight * (1.0 - (closes[i] - minValue) / range)
                    : midY;
                points.Add(new Point(x, y));
            }

            // 채우기 영역 (그라데이션)
            var fillPoints = new PointCollection(points)
            {
                new Point(points[points.Count - 1].X, padding + innerHeight),
                new Point(points[0].X, padding + innerHeight),
            };
            var fillPolygon = new Polygon
            {
                Points = fillPoints,
                Fill = brushChartFill,
                Stroke = null,
                IsHitTestVisible = false,
            };
            ChartCanvas.Children.Add(fillPolygon);

            // 라인
            var polyline = new Polyline
            {
                Points = points,
                Stroke = brushAccent,
                StrokeThickness = 2.0,
                StrokeLineJoin = PenLineJoin.Round,
                StrokeStartLineCap = PenLineCap.Round,
                StrokeEndLineCap = PenLineCap.Round,
            };
            ChartCanvas.Children.Add(polyline);

            // 베이스라인 (시작가 기준)
            var baseValue = closes[0];
            var baseY = hasRange
                ? padding + innerHeight * (1.0 - (baseValue - minValue) / range)
                : midY;
            var baseLine = new Line
            {
                X1 = padding,
                X2 = padding + innerWidth,
                Y1 = baseY,
                Y2 = baseY,
                Stroke = brushTextSecondary,
                StrokeThickness = 1.0,
                StrokeDashArray = new DoubleCollection { 4, 4 },
                Opacity = 0.45,
            };
            ChartCanvas.Children.Add(baseLine);

            // 마지막 포인트 강조
            var lastPoint = points[points.Count - 1];
            var dot = new Ellipse
            {
                Width = 10,
                Height = 10,
                Fill = brushAccent,
                Stroke = Brushes.White,
                StrokeThickness = 1.5,
            };
            Canvas.SetLeft(dot, lastPoint.X - 5);
            Canvas.SetTop(dot, lastPoint.Y - 5);
            ChartCanvas.Children.Add(dot);
        }

        private void clearChart()
        {
            ChartCanvas.Children.Clear();
            ChartPlaceholderLabel.Visibility = Visibility.Visible;
            lastClosePrices = null;
        }

        private void setLoading(bool loading)
        {
            isLoading = loading;
            LoadingBar.Visibility = loading ? Visibility.Visible : Visibility.Collapsed;
            SearchButton.IsEnabled = !loading;
            SymbolTextBox.IsEnabled = !loading;
        }

        private void showStatus(string message, StatusKind kind)
        {
            StatusLabel.Text = message;
            StatusLabel.Foreground = kind switch
            {
                StatusKind.Success => brushPositive,
                StatusKind.Warning => brushWarning,
                StatusKind.Error => brushNegative,
                _ => brushTextSecondary,
            };
        }

        private static bool isValidSymbolFormat(string symbol)
        {
            if (string.IsNullOrEmpty(symbol) || symbol.Length > 15) return false;
            foreach (var ch in symbol)
            {
                var ok = (ch >= 'A' && ch <= 'Z')
                         || (ch >= '0' && ch <= '9')
                         || ch == '.'
                         || ch == '-';
                if (!ok) return false;
            }
            return true;
        }

        private static string formatMoney(double? value, string? currency)
        {
            if (!value.HasValue) return "—";
            var formatted = value.Value.ToString("N2", CultureInfo.InvariantCulture);
            return string.IsNullOrEmpty(currency) ? formatted : $"{formatted} {currency}";
        }

        private static string formatInteger(long? value)
        {
            if (!value.HasValue) return "—";
            return value.Value.ToString("N0", CultureInfo.InvariantCulture);
        }

        private static string formatCompactCurrency(long? value, string? currency)
        {
            if (!value.HasValue) return "—";
            var absVal = Math.Abs(value.Value);
            string text;
            if (absVal >= 1_000_000_000_000L)
                text = (value.Value / 1_000_000_000_000.0).ToString("F2", CultureInfo.InvariantCulture) + "T";
            else if (absVal >= 1_000_000_000L)
                text = (value.Value / 1_000_000_000.0).ToString("F2", CultureInfo.InvariantCulture) + "B";
            else if (absVal >= 1_000_000L)
                text = (value.Value / 1_000_000.0).ToString("F2", CultureInfo.InvariantCulture) + "M";
            else
                text = value.Value.ToString("N0", CultureInfo.InvariantCulture);
            return string.IsNullOrEmpty(currency) ? text : $"{text} {currency}";
        }

        private static string combineParts(params string?[] parts)
        {
            var filtered = parts.Where(p => !string.IsNullOrWhiteSpace(p)).ToArray();
            return filtered.Length == 0 ? "" : string.Join(" · ", filtered);
        }

        private enum StatusKind { Info, Success, Warning, Error }
    }

    internal sealed class StockApiException : Exception
    {
        public StockApiException(string message) : base(message) { }
    }

    internal sealed class StockSummary
    {
        [JsonPropertyName("symbol")] public string? Symbol { get; set; }
        [JsonPropertyName("name")] public string? Name { get; set; }
        [JsonPropertyName("price")] public double? Price { get; set; }
        [JsonPropertyName("prev_close")] public double? PrevClose { get; set; }
        [JsonPropertyName("change")] public double? Change { get; set; }
        [JsonPropertyName("change_percent")] public double? ChangePercent { get; set; }
        [JsonPropertyName("open")] public double? Open { get; set; }
        [JsonPropertyName("high")] public double? High { get; set; }
        [JsonPropertyName("low")] public double? Low { get; set; }
        [JsonPropertyName("volume")] public long? Volume { get; set; }
        [JsonPropertyName("average_volume")] public long? AverageVolume { get; set; }
        [JsonPropertyName("market_cap")] public long? MarketCap { get; set; }
        [JsonPropertyName("fifty_two_week_high")] public double? FiftyTwoWeekHigh { get; set; }
        [JsonPropertyName("fifty_two_week_low")] public double? FiftyTwoWeekLow { get; set; }
        [JsonPropertyName("currency")] public string? Currency { get; set; }
        [JsonPropertyName("exchange")] public string? Exchange { get; set; }
        [JsonPropertyName("sector")] public string? Sector { get; set; }
        [JsonPropertyName("industry")] public string? Industry { get; set; }
        [JsonPropertyName("quote_type")] public string? QuoteType { get; set; }
    }

    internal sealed class StockHistory
    {
        [JsonPropertyName("symbol")] public string? Symbol { get; set; }
        [JsonPropertyName("range")] public string? Range { get; set; }
        [JsonPropertyName("interval")] public string? Interval { get; set; }
        [JsonPropertyName("prices")] public List<StockPricePoint> Prices { get; set; } = new();
    }

    internal sealed class StockPricePoint
    {
        [JsonPropertyName("date")] public string? Date { get; set; }
        [JsonPropertyName("open")] public double? Open { get; set; }
        [JsonPropertyName("high")] public double? High { get; set; }
        [JsonPropertyName("low")] public double? Low { get; set; }
        [JsonPropertyName("close")] public double? Close { get; set; }
        [JsonPropertyName("volume")] public long? Volume { get; set; }
    }

    internal sealed class ApiErrorEnvelope
    {
        [JsonPropertyName("error")] public ApiErrorPayload? Error { get; set; }
    }

    internal sealed class ApiErrorPayload
    {
        [JsonPropertyName("code")] public string? Code { get; set; }
        [JsonPropertyName("message")] public string? Message { get; set; }
    }
}
