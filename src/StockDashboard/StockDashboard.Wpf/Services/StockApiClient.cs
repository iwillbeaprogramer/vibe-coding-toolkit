using System;
using System.Net;
using System.Net.Http;
using System.Net.Http.Json;
using System.Threading;
using System.Threading.Tasks;
using StockDashboard.Wpf.Models;

namespace StockDashboard.Wpf.Services;

public sealed class StockApiClient : IStockApiClient
{
    private readonly HttpClient _httpClient;

    public StockApiClient(HttpClient? httpClient = null, Uri? baseAddress = null)
    {
        _httpClient = httpClient ?? new HttpClient();
        _httpClient.BaseAddress ??= baseAddress ?? new Uri("http://127.0.0.1:8000/");
        _httpClient.Timeout = TimeSpan.FromSeconds(10);
    }

    public async Task<StockDetailDto> GetStockDetailAsync(string symbol, string range, CancellationToken ct = default)
    {
        var path = $"api/stock/{Uri.EscapeDataString(symbol)}?range={Uri.EscapeDataString(range)}";
        HttpResponseMessage response;
        try
        {
            response = await _httpClient.GetAsync(path, ct).ConfigureAwait(false);
        }
        catch (HttpRequestException ex)
        {
            throw new StockApiException(0, "network_error",
                "백엔드 서버에 연결할 수 없습니다. FastAPI 서버가 실행 중인지 확인해 주세요.")
            { };
        }
        catch (TaskCanceledException ex)
        {
            if (ct.IsCancellationRequested)
            {
                throw new OperationCanceledException("사용자에 의해 검색 요청이 취소되었습니다.", ex, ct);
            }
            throw new StockApiException(0, "timeout", "요청이 시간 초과되었습니다.");
        }

        if (!response.IsSuccessStatusCode)
        {
            ApiErrorDto? error = null;
            try
            {
                error = await response.Content.ReadFromJsonAsync<ApiErrorDto>(cancellationToken: ct).ConfigureAwait(false);
            }
            catch
            {
                // ignored: fall through to generic message
            }

            var message = error?.Message ?? response.ReasonPhrase ?? "알 수 없는 오류";
            throw new StockApiException((int)response.StatusCode, error?.ErrorCode, message);
        }

        var dto = await response.Content.ReadFromJsonAsync<StockDetailDto>(cancellationToken: ct).ConfigureAwait(false);
        if (dto is null)
        {
            throw new StockApiException(500, "empty_body", "백엔드 응답 본문이 비어 있습니다.");
        }
        return dto;
    }
}
