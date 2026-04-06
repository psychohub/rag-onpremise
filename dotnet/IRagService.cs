using RagOnPremise.Models;

namespace RagOnPremise.Services
{
    public interface IRagService
    {
        Task<RagQueryResponse> QueryAsync(RagQueryRequest request);
        Task<bool> TestConnectionAsync();
    }
}
