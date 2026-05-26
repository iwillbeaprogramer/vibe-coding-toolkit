using System.Threading;
using System.Threading.Tasks;
using StockDashboard.Wpf.Models;

namespace StockDashboard.Wpf.Services;

public interface IStockApiClient
{
    Task<StockDetailDto> GetStockDetailAsync(string symbol, string range, CancellationToken ct = default);
}

public sealed class StockApiException : System.Exception
{
    public int StatusCode { get; }
    public string? ErrorCode { get; }

    public StockApiException(int statusCode, string? errorCode, string message)
        : base(message)
    {
        StatusCode = statusCode;
        ErrorCode = errorCode;
    }
}
