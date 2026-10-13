import 'package:flutter/material.dart';
import '../models/product.dart';
import '../services/api_service.dart';
import '../services/auth_service.dart';
import '../services/catalog_service.dart';

class AdminCatalogScreen extends StatefulWidget {
  const AdminCatalogScreen({super.key});

  @override
  State<AdminCatalogScreen> createState() => _AdminCatalogScreenState();
}

class _AdminCatalogScreenState extends State<AdminCatalogScreen> {
  List<Product> _allProducts = [];
  List<Product> _filteredProducts = [];
  bool _isLoading = true;
  bool _isSyncing = false;
  String _searchQuery = '';
  String _selectedCategory = 'semua';
  Map<String, dynamic> _stats = {};

  final List<String> _categories = ['semua', 'laptop', 'desktop', 'printer', 'monitor'];

  @override
  void initState() {
    super.initState();
    _checkAuthAndLoad();
  }

  Future<void> _checkAuthAndLoad() async {
    final loggedIn = await AuthService.isLoggedIn();
    if (!loggedIn) {
      if (mounted) {
        Navigator.pushReplacementNamed(context, '/login');
      }
      return;
    }
    await _loadData();
  }

  Future<void> _loadData() async {
    setState(() => _isLoading = true);
    try {
      final prods = await CatalogService.fetchProducts();
      final stats = await CatalogService.fetchStats();
      if (mounted) {
        setState(() {
          _allProducts = prods;
          _stats = stats;
          _applyFilter();
          _isLoading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() => _isLoading = false);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Gagal memuat katalog: $e'), backgroundColor: Colors.red),
        );
      }
    }
  }

  void _applyFilter() {
    _filteredProducts = _allProducts.where((p) {
      final matchCat = _selectedCategory == 'semua' || p.kategori.toLowerCase() == _selectedCategory;
      final q = _searchQuery.toLowerCase();
      final matchQuery = q.isEmpty ||
          p.nama.toLowerCase().contains(q) ||
          p.kode.toLowerCase().contains(q) ||
          p.brand.toLowerCase().contains(q) ||
          p.prosesor.toLowerCase().contains(q);
      return matchCat && matchQuery;
    }).toList();
  }

  Future<void> _handleSyncQdrant() async {
    setState(() => _isSyncing = true);
    try {
      final res = await CatalogService.syncQdrant();
      final count = res['synced_count'] ?? 0;
      if (mounted) {
        setState(() => _isSyncing = false);
        showDialog(
          context: context,
          builder: (ctx) => AlertDialog(
            title: const Row(
              children: [
                Icon(Icons.check_circle, color: Colors.green),
                SizedBox(width: 8),
                Text('Sinkronisasi Berhasil'),
              ],
            ),
            content: Text('Sebanyak $count produk telah berhasil di-vektorisasi dan disimpan ke Qdrant Vector DB!'),
            actions: [
              TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('OK')),
            ],
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        setState(() => _isSyncing = false);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Gagal sinkronisasi: $e'), backgroundColor: Colors.red),
        );
      }
    }
  }

  Future<void> _handleDelete(Product product) async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Hapus Produk?'),
        content: Text('Yakin ingin menghapus ${product.nama} (${product.kode}) dari katalog dan Qdrant?'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Batal')),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: Colors.red),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Hapus', style: TextStyle(color: Colors.white)),
          ),
        ],
      ),
    );

    if (confirm == true) {
      try {
        final ok = await CatalogService.deleteProduct(product.kode);
        if (ok) {
          await _loadData();
          if (mounted) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(content: Text('Produk ${product.kode} berhasil dihapus')),
            );
          }
        }
      } catch (e) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Gagal menghapus produk: $e'), backgroundColor: Colors.red),
          );
        }
      }
    }
  }

  void _openProductDialog([Product? existing]) {
    final isEdit = existing != null;
    final kodeController = TextEditingController(text: existing?.kode ?? '');
    final namaController = TextEditingController(text: existing?.nama ?? '');
    String kategori = existing?.kategori ?? 'laptop';
    final brandController = TextEditingController(text: existing?.brand ?? '');
    final hargaController = TextEditingController(text: existing?.harga.toString() ?? '');
    final stokController = TextEditingController(text: existing?.stok.toString() ?? '10');
    final prosesorController = TextEditingController(text: existing?.prosesor ?? '');
    final ramController = TextEditingController(text: existing?.ram ?? '');
    final storageController = TextEditingController(text: existing?.storage ?? '');
    final gpuController = TextEditingController(text: existing?.gpu ?? '');
    final layarController = TextEditingController(text: existing?.layar ?? '');
    final osController = TextEditingController(text: existing?.os ?? 'Windows 11 Home');
    final cocokController = TextEditingController(text: existing?.cocokUntuk ?? '');
    final deskripsiController = TextEditingController(text: existing?.deskripsi ?? '');
    final imgUrlController = TextEditingController(text: existing?.imageUrl ?? '');

    bool syncQdrant = true;
    bool isSaving = false;

    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (dialogCtx) {
        return StatefulBuilder(
          builder: (context, setDialogState) {
            return AlertDialog(
              title: Text(isEdit ? 'Edit Produk (${existing.kode})' : 'Tambah Produk Baru'),
              content: SizedBox(
                width: 680,
                child: SingleChildScrollView(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Row(
                        children: [
                          Expanded(
                            child: TextField(
                              controller: kodeController,
                              enabled: !isEdit,
                              decoration: const InputDecoration(
                                labelText: 'Kode Produk (misal: KB-L11)',
                                border: OutlineInputBorder(),
                              ),
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: DropdownButtonFormField<String>(
                              initialValue: kategori.toLowerCase(),
                              decoration: const InputDecoration(
                                labelText: 'Kategori',
                                border: OutlineInputBorder(),
                              ),
                              items: const [
                                DropdownMenuItem(value: 'laptop', child: Text('Laptop')),
                                DropdownMenuItem(value: 'desktop', child: Text('Desktop')),
                                DropdownMenuItem(value: 'printer', child: Text('Printer')),
                                DropdownMenuItem(value: 'monitor', child: Text('Monitor')),
                              ],
                              onChanged: (val) {
                                if (val != null) {
                                  setDialogState(() => kategori = val);
                                }
                              },
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 12),
                      Row(
                        children: [
                          Expanded(
                            flex: 2,
                            child: TextField(
                              controller: namaController,
                              decoration: const InputDecoration(
                                labelText: 'Nama Produk Lengkap',
                                border: OutlineInputBorder(),
                              ),
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            flex: 1,
                            child: TextField(
                              controller: brandController,
                              decoration: const InputDecoration(
                                labelText: 'Merek / Brand',
                                border: OutlineInputBorder(),
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 12),
                      Row(
                        children: [
                          Expanded(
                            child: TextField(
                              controller: hargaController,
                              keyboardType: TextInputType.number,
                              decoration: const InputDecoration(
                                labelText: 'Harga (Rupiah)',
                                prefixText: 'Rp ',
                                border: OutlineInputBorder(),
                              ),
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: TextField(
                              controller: stokController,
                              keyboardType: TextInputType.number,
                              decoration: const InputDecoration(
                                labelText: 'Stok Unit',
                                border: OutlineInputBorder(),
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 12),
                      Row(
                        children: [
                          Expanded(
                            child: TextField(
                              controller: prosesorController,
                              decoration: const InputDecoration(
                                labelText: 'Prosesor / CPU',
                                border: OutlineInputBorder(),
                              ),
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: TextField(
                              controller: ramController,
                              decoration: const InputDecoration(
                                labelText: 'RAM (misal: 16 GB DDR5)',
                                border: OutlineInputBorder(),
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 12),
                      Row(
                        children: [
                          Expanded(
                            child: TextField(
                              controller: storageController,
                              decoration: const InputDecoration(
                                labelText: 'Storage (misal: 512 GB NVMe SSD)',
                                border: OutlineInputBorder(),
                              ),
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: TextField(
                              controller: gpuController,
                              decoration: const InputDecoration(
                                labelText: 'GPU / Kartu Grafis',
                                border: OutlineInputBorder(),
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 12),
                      Row(
                        children: [
                          Expanded(
                            child: TextField(
                              controller: layarController,
                              decoration: const InputDecoration(
                                labelText: 'Layar / Resolusi',
                                border: OutlineInputBorder(),
                              ),
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: TextField(
                              controller: osController,
                              decoration: const InputDecoration(
                                labelText: 'Sistem Operasi',
                                border: OutlineInputBorder(),
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 12),
                      TextField(
                        controller: cocokController,
                        decoration: const InputDecoration(
                          labelText: 'Cocok Untuk (misal: gaming, desain, kuliah, kantor)',
                          border: OutlineInputBorder(),
                        ),
                      ),
                      const SizedBox(height: 12),
                      TextField(
                        controller: deskripsiController,
                        maxLines: 2,
                        decoration: const InputDecoration(
                          labelText: 'Deskripsi Produk',
                          border: OutlineInputBorder(),
                        ),
                      ),
                      const SizedBox(height: 12),
                      Row(
                        children: [
                          Expanded(
                            child: TextField(
                              controller: imgUrlController,
                              decoration: const InputDecoration(
                                labelText: 'URL Gambar Produk (https://... atau /uploads/...)',
                                border: OutlineInputBorder(),
                              ),
                              onChanged: (_) => setDialogState(() {}),
                            ),
                          ),
                          const SizedBox(width: 12),
                          Container(
                            width: 60,
                            height: 60,
                            decoration: BoxDecoration(
                              borderRadius: BorderRadius.circular(8),
                              border: Border.all(color: Colors.grey.shade300),
                            ),
                            child: ClipRRect(
                              borderRadius: BorderRadius.circular(8),
                              child: Image.network(
                                ApiService.resolveImageUrl(imgUrlController.text),
                                fit: BoxFit.cover,
                                errorBuilder: (_, _, _) => const Icon(Icons.image_not_supported, size: 28),
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 12),
                      CheckboxListTile(
                        title: const Text('Sinkronkan langsung ke Qdrant Vector DB'),
                        value: syncQdrant,
                        controlAffinity: ListTileControlAffinity.leading,
                        contentPadding: EdgeInsets.zero,
                        onChanged: (val) {
                          setDialogState(() => syncQdrant = val ?? true);
                        },
                      ),
                    ],
                  ),
                ),
              ),
              actions: [
                TextButton(
                  onPressed: isSaving ? null : () => Navigator.pop(dialogCtx),
                  child: const Text('Batal'),
                ),
                ElevatedButton(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.blue.shade700,
                    foregroundColor: Colors.white,
                  ),
                  onPressed: isSaving
                      ? null
                      : () async {
                          if (kodeController.text.trim().isEmpty || namaController.text.trim().isEmpty) {
                            ScaffoldMessenger.of(context).showSnackBar(
                              const SnackBar(content: Text('Kode dan Nama produk wajib diisi!')),
                            );
                            return;
                          }
                          setDialogState(() => isSaving = true);
                          final messenger = ScaffoldMessenger.of(context);
                          final navigator = Navigator.of(dialogCtx);
                          final p = Product(
                            kode: kodeController.text.trim().toUpperCase(),
                            nama: namaController.text.trim(),
                            kategori: kategori.toLowerCase(),
                            brand: brandController.text.trim(),
                            harga: int.tryParse(hargaController.text.trim()) ?? 0,
                            stok: int.tryParse(stokController.text.trim()) ?? 1,
                            prosesor: prosesorController.text.trim(),
                            ram: ramController.text.trim(),
                            storage: storageController.text.trim(),
                            gpu: gpuController.text.trim(),
                            layar: layarController.text.trim(),
                            os: osController.text.trim(),
                            cocokUntuk: cocokController.text.trim(),
                            deskripsi: deskripsiController.text.trim(),
                            imageUrl: imgUrlController.text.trim(),
                          );
                          try {
                            await CatalogService.saveProduct(p, syncQdrant: syncQdrant);
                            navigator.pop();
                            await _loadData();
                            messenger.showSnackBar(
                              SnackBar(content: Text('Produk ${p.kode} berhasil disimpan!')),
                            );
                          } catch (err) {
                            setDialogState(() => isSaving = false);
                            messenger.showSnackBar(
                              SnackBar(content: Text('Gagal menyimpan: $err'), backgroundColor: Colors.red),
                            );
                          }
                        },
                  child: isSaving
                      ? const SizedBox(
                          width: 16,
                          height: 16,
                          child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2),
                        )
                      : Text(isEdit ? 'Simpan Perubahan' : 'Tambah Produk'),
                ),
              ],
            );
          },
        );
      },
    );
  }

  Future<void> _handleLogout() async {
    await AuthService.logout();
    if (mounted) {
      Navigator.pushReplacementNamed(context, '/login');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF1F5F9),
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 1,
        title: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(6),
              decoration: BoxDecoration(
                color: Colors.blue.shade50,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Icon(Icons.inventory_2_rounded, color: Colors.blue.shade700, size: 22),
            ),
            const SizedBox(width: 12),
            const Text(
              'Bobby Computer — Manajemen Katalog & AI',
              style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Color(0xFF0F172A)),
            ),
          ],
        ),
        actions: [
          OutlinedButton.icon(
            icon: const Icon(Icons.chat_bubble_outline, size: 16),
            label: const Text('Live Chat Pelanggan'),
            onPressed: () => Navigator.pushNamed(context, '/'),
          ),
          const SizedBox(width: 12),
          IconButton(
            tooltip: 'Logout Admin',
            icon: const Icon(Icons.logout_rounded, color: Colors.red),
            onPressed: _handleLogout,
          ),
          const SizedBox(width: 16),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : Padding(
              padding: const EdgeInsets.all(24.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Top stats & Actions Bar
                  _buildStatsAndActions(),
                  const SizedBox(height: 20),

                  // Filter & Search bar
                  _buildFilterBar(),
                  const SizedBox(height: 16),

                  // Table
                  Expanded(child: _buildProductTable()),
                ],
              ),
            ),
    );
  }

  Widget _buildStatsAndActions() {
    return Row(
      children: [
        // Stats chips
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(10),
            border: Border.all(color: Colors.grey.shade300),
          ),
          child: Row(
            children: [
              const Icon(Icons.devices, size: 18, color: Colors.blue),
              const SizedBox(width: 8),
              Text(
                'Total: ${_allProducts.length} Produk',
                style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
              ),
            ],
          ),
        ),
        if (_stats['active_sessions'] != null) ...[
          const SizedBox(width: 8),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: Colors.grey.shade300),
            ),
            child: Row(
              children: [
                const Icon(Icons.forum_outlined, size: 18, color: Colors.green),
                const SizedBox(width: 6),
                Text(
                  '${_stats['active_sessions']} Sesi Chat',
                  style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
                ),
              ],
            ),
          ),
        ],
        const Spacer(),

        // Sync Qdrant button
        ElevatedButton.icon(
          icon: _isSyncing
              ? const SizedBox(
                  width: 16,
                  height: 16,
                  child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                )
              : const Icon(Icons.sync_rounded, size: 18),
          label: Text(_isSyncing ? 'Menyinkronkan...' : 'Sinkronisasi ke Qdrant AI'),
          style: ElevatedButton.styleFrom(
            backgroundColor: const Color(0xFF0284C7),
            foregroundColor: Colors.white,
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
          ),
          onPressed: _isSyncing ? null : _handleSyncQdrant,
        ),
        const SizedBox(width: 12),

        // Add Product button
        ElevatedButton.icon(
          icon: const Icon(Icons.add, size: 18),
          label: const Text('Tambah Produk'),
          style: ElevatedButton.styleFrom(
            backgroundColor: Colors.blue.shade700,
            foregroundColor: Colors.white,
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
          ),
          onPressed: () => _openProductDialog(),
        ),
      ],
    );
  }

  Widget _buildFilterBar() {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.grey.shade200),
      ),
      child: Row(
        children: [
          // Search box
          Expanded(
            flex: 2,
            child: TextField(
              decoration: InputDecoration(
                hintText: 'Cari berdasarkan nama, kode, CPU...',
                prefixIcon: const Icon(Icons.search, size: 20),
                isDense: true,
                contentPadding: const EdgeInsets.symmetric(vertical: 10, horizontal: 12),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(8),
                  borderSide: BorderSide(color: Colors.grey.shade300),
                ),
              ),
              onChanged: (val) {
                setState(() {
                  _searchQuery = val;
                  _applyFilter();
                });
              },
            ),
          ),
          const SizedBox(width: 16),

          // Category filter
          Wrap(
            spacing: 6,
            children: _categories.map((cat) {
              final isSel = _selectedCategory == cat;
              return ChoiceChip(
                label: Text(
                  cat[0].toUpperCase() + cat.substring(1),
                  style: TextStyle(
                    fontSize: 12.5,
                    fontWeight: isSel ? FontWeight.bold : FontWeight.normal,
                    color: isSel ? Colors.white : Colors.black87,
                  ),
                ),
                selected: isSel,
                selectedColor: Colors.blue.shade700,
                onSelected: (selected) {
                  if (selected) {
                    setState(() {
                      _selectedCategory = cat;
                      _applyFilter();
                    });
                  }
                },
              );
            }).toList(),
          ),
        ],
      ),
    );
  }

  Widget _buildProductTable() {
    if (_filteredProducts.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.search_off_rounded, size: 48, color: Colors.grey.shade400),
            const SizedBox(height: 8),
            Text(
              'Tidak ada produk yang cocok dengan pencarian.',
              style: TextStyle(color: Colors.grey.shade600),
            ),
          ],
        ),
      );
    }

    return Card(
      elevation: 1,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(12),
        child: SingleChildScrollView(
          scrollDirection: Axis.vertical,
          child: SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: DataTable(
              headingRowColor: WidgetStateProperty.all(const Color(0xFFF8FAFC)),
              columns: const [
                DataColumn(label: Text('Foto', style: TextStyle(fontWeight: FontWeight.bold))),
                DataColumn(label: Text('Kode', style: TextStyle(fontWeight: FontWeight.bold))),
                DataColumn(label: Text('Nama Produk', style: TextStyle(fontWeight: FontWeight.bold))),
                DataColumn(label: Text('Kategori', style: TextStyle(fontWeight: FontWeight.bold))),
                DataColumn(label: Text('Harga', style: TextStyle(fontWeight: FontWeight.bold))),
                DataColumn(label: Text('Stok', style: TextStyle(fontWeight: FontWeight.bold))),
                DataColumn(label: Text('Spesifikasi', style: TextStyle(fontWeight: FontWeight.bold))),
                DataColumn(label: Text('Aksi', style: TextStyle(fontWeight: FontWeight.bold))),
              ],
              rows: _filteredProducts.map((p) {
                return DataRow(
                  cells: [
                    DataCell(
                      Container(
                        width: 44,
                        height: 44,
                        decoration: BoxDecoration(
                          borderRadius: BorderRadius.circular(6),
                          border: Border.all(color: Colors.grey.shade200),
                        ),
                        child: ClipRRect(
                          borderRadius: BorderRadius.circular(6),
                          child: Image.network(
                            ApiService.resolveImageUrl(p.imageUrl),
                            fit: BoxFit.cover,
                            errorBuilder: (_, _, _) => const Icon(Icons.devices, size: 24, color: Colors.grey),
                          ),
                        ),
                      ),
                    ),
                    DataCell(Text(p.kode, style: const TextStyle(fontWeight: FontWeight.w600))),
                    DataCell(
                      ConstrainedBox(
                        constraints: const BoxConstraints(maxWidth: 240),
                        child: Text(p.nama, overflow: TextOverflow.ellipsis),
                      ),
                    ),
                    DataCell(
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                        decoration: BoxDecoration(
                          color: Colors.blue.shade50,
                          borderRadius: BorderRadius.circular(6),
                        ),
                        child: Text(
                          p.kategori.toUpperCase(),
                          style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: Colors.blue.shade800),
                        ),
                      ),
                    ),
                    DataCell(Text(p.formattedPrice, style: const TextStyle(fontWeight: FontWeight.w600))),
                    DataCell(Text('${p.stok}')),
                    DataCell(
                      ConstrainedBox(
                        constraints: const BoxConstraints(maxWidth: 200),
                        child: Text(
                          '${p.prosesor} • ${p.ram}',
                          overflow: TextOverflow.ellipsis,
                          style: TextStyle(fontSize: 12, color: Colors.grey.shade700),
                        ),
                      ),
                    ),
                    DataCell(
                      Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          IconButton(
                            icon: const Icon(Icons.edit_outlined, size: 18, color: Colors.blue),
                            tooltip: 'Edit Produk',
                            onPressed: () => _openProductDialog(p),
                          ),
                          IconButton(
                            icon: const Icon(Icons.delete_outline, size: 18, color: Colors.red),
                            tooltip: 'Hapus Produk',
                            onPressed: () => _handleDelete(p),
                          ),
                        ],
                      ),
                    ),
                  ],
                );
              }).toList(),
            ),
          ),
        ),
      ),
    );
  }
}
