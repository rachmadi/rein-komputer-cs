class ApiService {
  // Backend URL dinamis:
  // Mengikuti origin aktif di browser (misal https://xxx.trycloudflare.com atau http://localhost:8000)
  static String get baseUrl {
    try {
      if (Uri.base.scheme.startsWith('http')) {
        return Uri.base.origin;
      }
    } catch (_) {}
    return 'http://localhost:8000';
  }

  static String resolveImageUrl(String? rawUrl) {
    if (rawUrl == null || rawUrl.trim().isEmpty) {
      return 'https://images.unsplash.com/photo-1517336714731-489689fd1ca8?auto=format&fit=crop&w=400&q=80';
    }
    final trimmed = rawUrl.trim();
    if (trimmed.startsWith('http://') || trimmed.startsWith('https://')) {
      return trimmed;
    }
    if (trimmed.startsWith('/')) {
      return '$baseUrl$trimmed';
    }
    return '$baseUrl/$trimmed';
  }
}
