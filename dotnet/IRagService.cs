using RagOnPremise.Models;

namespace RagOnPremise.Services
{
    public interface IRagService
    {
        Task<RagQueryResponse> QueryAsync(
            RagQueryRequest request,
            CancellationToken cancellationToken = default);

        Task<bool> TestConnectionAsync(CancellationToken cancellationToken = default);
    }
}
