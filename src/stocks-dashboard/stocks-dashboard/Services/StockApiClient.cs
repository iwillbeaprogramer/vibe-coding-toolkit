using System;
using System.Configuration;
using System.Net;
using System.Net.Http;
using System.Net.Http.Json;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using stocks_dashboard.Models;

namespace stocks_dashboard.Services
{
    public class StockApiException : Exception
    {
        public string UserMessage { get; }
        public StockApiException(string userMessage, Exception? inner = null)
            : base(userMessage, inner)
        {
            UserMessage = userMessage;
        }
    }

    public class StockApiClient
    {
        private readonly HttpClient _http;
        private readonly string _range;
        private readonly string _interval;

        public StockApiClient()
        {
            var baseUrl = ConfigurationManager.AppSettings["StocksApiBaseUrl"] ?? "http://127.0.0.1:8000";
            var timeoutSeconds = int.TryParse(ConfigurationManager.AppSettings["StocksApiTimeoutSeconds"], out var t) ? t : 20;
            _range = ConfigurationManager.AppSettings["DefaultChartRange"] ?? "6mo";
            _interval = ConfigurationManager.AppSettings["DefaultChartInterval"] ?? "1d";

            _http = new HttpClient
            {
                BaseAddress = new Uri(baseUrl.TrimEnd('/') + "/"),
                Timeout = TimeSpan.FromSeconds(timeoutSeconds)
            };
        }

        public async Task<StockDetailDto> FetchStockAsync(string symbol, CancellationToken ct = default)
        {
            var url = $"api/stocks/{Uri.EscapeDataString(symbol)}?range={_range}&interval={_interval}";

            HttpResponseMessage response;
            try
            {
                response = await _http.GetAsync(url, ct).ConfigureAwait(false);
            }
            catch (TaskCanceledException ex) when (!ct.IsCancellationRequested)
            {
                throw new StockApiException(
                    "API 응답 대기 시간이 초과되었습니다. 잠시 후 다시 시도해 주세요.", ex);
            }
            catch (HttpRequestException ex)
            {
                throw new StockApiException(
                    "API 서버에 접속할 수 없습니다. 로컬 백엔드(FastAPI)가 실행 중인지 확인해 주세요.", ex);
            }

            if (response.IsSuccessStatusCode)
            {
                try
                {
                    var result = await response.Content.ReadFromJsonAsync<StockDetailDto>(cancellationToken: ct)
                        .ConfigureAwait(false);
                    if (result == null)
                    {
                        throw new StockApiException("API 응답을 해석할 수 없습니다.");
                    }
                    return result;
                }
                catch (JsonException ex)
                {
                    throw new StockApiException("API 응답 형식이 올바르지 않습니다.", ex);
                }
            }

            string? code = null;
            string? message = null;
            try
            {
                var error = await response.Content.ReadFromJsonAsync<ApiErrorDto>(cancellationToken: ct)
                    .ConfigureAwait(false);
                code = error?.Code;
                message = error?.Message;
            }
            catch
            {
                // ignore - fall through to status-based message
            }

            throw new StockApiException(MapErrorMessage(response.StatusCode, code, message));
        }

        private static string MapErrorMessage(HttpStatusCode status, string? code, string? message)
        {
            if (!string.IsNullOrWhiteSpace(message))
            {
                return message!;
            }
            return status switch
            {
                HttpStatusCode.BadRequest => "잘못된 입력입니다. 티커 형식을 확인해 주세요.",
                HttpStatusCode.NotFound => "해당 티커를 찾을 수 없습니다.",
                HttpStatusCode.BadGateway => "시세 공급자 일시적 장애입니다. 잠시 후 다시 시도해 주세요.",
                HttpStatusCode.ServiceUnavailable => "시세 공급자 일시적 장애입니다. 잠시 후 다시 시도해 주세요.",
                _ => $"API 오류가 발생했습니다. (HTTP {(int)status})"
            };
        }
    }
}
