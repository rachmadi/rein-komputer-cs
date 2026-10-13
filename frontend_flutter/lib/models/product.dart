import 'package:intl/intl.dart';

class Product {
  final String kode;
  final String nama;
  final String kategori;
  final String brand;
  final int harga;
  final String prosesor;
  final String ram;
  final String storage;
  final String gpu;
  final String layar;
  final String os;
  final int stok;
  final String deskripsi;
  final String cocokUntuk;
  final String imageUrl;

  Product({
    required this.kode,
    required this.nama,
    required this.kategori,
    required this.brand,
    required this.harga,
    required this.prosesor,
    required this.ram,
    required this.storage,
    required this.gpu,
    required this.layar,
    required this.os,
    required this.stok,
    required this.deskripsi,
    required this.cocokUntuk,
    required this.imageUrl,
  });

  factory Product.fromJson(Map<String, dynamic> json) {
    return Product(
      kode: json['kode'] ?? '',
      nama: json['nama'] ?? '',
      kategori: json['kategori'] ?? 'laptop',
      brand: json['brand'] ?? '',
      harga: (json['harga'] is int)
          ? json['harga']
          : int.tryParse(json['harga']?.toString() ?? '0') ?? 0,
      prosesor: json['prosesor'] ?? '',
      ram: json['ram'] ?? '',
      storage: json['storage'] ?? '',
      gpu: json['gpu'] ?? '',
      layar: json['layar'] ?? '',
      os: json['os'] ?? '',
      stok: (json['stok'] is int)
          ? json['stok']
          : int.tryParse(json['stok']?.toString() ?? '0') ?? 0,
      deskripsi: json['deskripsi'] ?? '',
      cocokUntuk: json['cocok_untuk'] ?? '',
      imageUrl: json['image_url'] ?? '',
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'kode': kode,
      'nama': nama,
      'kategori': kategori,
      'brand': brand,
      'harga': harga,
      'prosesor': prosesor,
      'ram': ram,
      'storage': storage,
      'gpu': gpu,
      'layar': layar,
      'os': os,
      'stok': stok,
      'deskripsi': deskripsi,
      'cocok_untuk': cocokUntuk,
      'image_url': imageUrl,
    };
  }

  String get formattedPrice {
    final currencyFormatter = NumberFormat.currency(
      locale: 'id_ID',
      symbol: 'Rp',
      decimalDigits: 0,
    );
    return currencyFormatter.format(harga);
  }
}
