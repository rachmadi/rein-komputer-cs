import 'dart:convert';
import 'package:http/http.dart' as http;
import '../models/product.dart';
import 'api_service.dart';
import 'auth_service.dart';

class CatalogService {
  static Future<List<Product>> fetchProducts() async {
    final headers = await AuthService.getAuthHeaders();
    final url = Uri.parse('${ApiService.baseUrl}/api/admin/products');

    final response = await http.get(url, headers: headers);
    if (response.statusCode == 200) {
      final List data = jsonDecode(utf8.decode(response.bodyBytes));
      return data.map((json) => Product.fromJson(json)).toList();
    } else {
      throw Exception('Gagal memuat produk: ${response.statusCode}');
    }
  }

  static Future<Product> saveProduct(Product product, {bool syncQdrant = true}) async {
    final headers = await AuthService.getAuthHeaders();
    final url = Uri.parse('${ApiService.baseUrl}/api/admin/products?sync_qdrant=$syncQdrant');

    final response = await http.post(
      url,
      headers: headers,
      body: jsonEncode(product.toJson()),
    );

    if (response.statusCode == 200) {
      final data = jsonDecode(utf8.decode(response.bodyBytes));
      return Product.fromJson(data['product']);
    } else {
      throw Exception('Gagal menyimpan produk: ${response.body}');
    }
  }

  static Future<bool> deleteProduct(String kode, {bool syncQdrant = true}) async {
    final headers = await AuthService.getAuthHeaders();
    final url = Uri.parse('${ApiService.baseUrl}/api/admin/products/$kode?sync_qdrant=$syncQdrant');

    final response = await http.delete(url, headers: headers);
    return response.statusCode == 200;
  }

  static Future<Map<String, dynamic>> syncQdrant() async {
    final headers = await AuthService.getAuthHeaders();
    final url = Uri.parse('${ApiService.baseUrl}/api/admin/sync-qdrant');

    final response = await http.post(url, headers: headers);
    if (response.statusCode == 200) {
      return jsonDecode(utf8.decode(response.bodyBytes));
    } else {
      throw Exception('Gagal sinkronisasi Qdrant: ${response.body}');
    }
  }

  static Future<Map<String, dynamic>> fetchStats() async {
    final headers = await AuthService.getAuthHeaders();
    final url = Uri.parse('${ApiService.baseUrl}/api/admin/stats');

    final response = await http.get(url, headers: headers);
    if (response.statusCode == 200) {
      return jsonDecode(utf8.decode(response.bodyBytes));
    }
    return {'total_products': 0, 'categories': {}, 'active_sessions': 0};
  }

  static Future<String> uploadImage(List<int> bytes, String filename) async {
    final token = await AuthService.getToken();
    final url = Uri.parse('${ApiService.baseUrl}/api/admin/upload-image');

    final request = http.MultipartRequest('POST', url);
    if (token != null) {
      request.headers['Authorization'] = 'Bearer $token';
    }

    final multipartFile = http.MultipartFile.fromBytes(
      'file',
      bytes,
      filename: filename,
    );
    request.files.add(multipartFile);

    final streamedResponse = await request.send();
    final response = await http.Response.fromStream(streamedResponse);

    if (response.statusCode == 200) {
      final data = jsonDecode(utf8.decode(response.bodyBytes));
      return data['url'] ?? '';
    } else {
      throw Exception('Gagal upload gambar: ${response.body}');
    }
  }
}
