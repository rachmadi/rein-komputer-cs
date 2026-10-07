import 'package:flutter/material.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import '../models/chat_message.dart';
import '../models/product.dart';
import '../services/api_service.dart';
import '../services/chat_service.dart';

class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final TextEditingController _textController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  final List<ChatMessage> _messages = [];
  bool _isLoading = false;
  bool _isInit = true;

  final List<String> _quickSuggestions = [
    'Laptop Acer ada apa aja?',
    'Rekomendasi laptop gaming RTX',
    'Desktop Lenovo untuk kantor',
    'Printer Canon infus resmi',
    'Laptop murah untuk mahasiswa',
  ];

  @override
  void initState() {
    super.initState();
    _loadHistory();
  }

  @override
  void dispose() {
    _textController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  Future<void> _loadHistory() async {
    try {
      final history = await ChatService.getHistory();
      if (mounted) {
        setState(() {
          _messages.clear();
          _messages.addAll(history);
          _isInit = false;
        });
        _scrollToBottom();
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _isInit = false;
        });
      }
    }
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent + 200,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  Future<void> _handleSend([String? presetText]) async {
    final text = (presetText ?? _textController.text).trim();
    if (text.isEmpty || _isLoading) return;

    if (presetText == null) {
      _textController.clear();
    }

    final userMsg = ChatMessage(
      text: text,
      isUser: true,
      timestamp: DateTime.now(),
    );

    setState(() {
      _messages.add(userMsg);
      _isLoading = true;
    });
    _scrollToBottom();

    try {
      final assistantMsg = await ChatService.sendMessage(text);
      if (mounted) {
        setState(() {
          _messages.add(assistantMsg);
          _isLoading = false;
        });
        _scrollToBottom();
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _messages.add(ChatMessage(
            text: 'Maaf Kak, terjadi kendala saat menghubungi server. Mohon pastikan backend aktif dan coba lagi ya!',
            isUser: false,
            timestamp: DateTime.now(),
          ));
          _isLoading = false;
        });
        _scrollToBottom();
      }
    }
  }

  Future<void> _handleReset() async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Reset Percakapan?'),
        content: const Text(
          'Seluruh riwayat chat saat ini akan dihapus dan sesi baru akan dimulai.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Batal'),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: Colors.red.shade600),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Reset', style: TextStyle(color: Colors.white)),
          ),
        ],
      ),
    );

    if (confirm == true) {
      setState(() => _isLoading = true);
      await ChatService.resetSession();
      setState(() {
        _messages.clear();
        _isLoading = false;
      });
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Sesi percakapan baru telah dibuat!')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF8FAFC),
      appBar: AppBar(
        elevation: 1,
        backgroundColor: Colors.white,
        titleSpacing: 16,
        title: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: Colors.blue.shade50,
                borderRadius: BorderRadius.circular(10),
              ),
              child: Icon(Icons.computer_rounded, color: Colors.blue.shade700, size: 24),
            ),
            const SizedBox(width: 12),
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                const Text(
                  'Bobby Computer CS',
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.bold,
                    color: Color(0xFF0F172A),
                  ),
                ),
                Row(
                  children: [
                    Container(
                      width: 8,
                      height: 8,
                      decoration: const BoxDecoration(
                        color: Colors.green,
                        shape: BoxShape.circle,
                      ),
                    ),
                    const SizedBox(width: 6),
                    Text(
                      'AI Customer Care • Online 24/7',
                      style: TextStyle(fontSize: 12, color: Colors.grey.shade600),
                    ),
                  ],
                ),
              ],
            ),
          ],
        ),
        actions: [
          IconButton(
            tooltip: 'Mulai Sesi Baru / Reset',
            icon: const Icon(Icons.refresh_rounded, color: Color(0xFF475569)),
            onPressed: _handleReset,
          ),
          const SizedBox(width: 4),
          Padding(
            padding: const EdgeInsets.only(right: 16.0),
            child: OutlinedButton.icon(
              icon: const Icon(Icons.admin_panel_settings, size: 16),
              label: const Text('Admin Portal'),
              style: OutlinedButton.styleFrom(
                foregroundColor: Colors.blue.shade700,
                side: BorderSide(color: Colors.blue.shade200),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
              ),
              onPressed: () {
                Navigator.pushNamed(context, '/login');
              },
            ),
          ),
        ],
      ),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 960),
          child: Column(
            children: [
              // Chat message area
              Expanded(
                child: _isInit
                    ? const Center(child: CircularProgressIndicator())
                    : _messages.isEmpty
                        ? _buildWelcomeState()
                        : ListView.builder(
                            controller: _scrollController,
                            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 20),
                            itemCount: _messages.length,
                            itemBuilder: (context, index) {
                              final msg = _messages[index];
                              return _buildMessageItem(msg);
                            },
                          ),
              ),

              // Loading bubble
              if (_isLoading) _buildTypingIndicator(),

              // Quick suggestions chips
              _buildSuggestionsBar(),

              // Input bar
              _buildInputArea(),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildWelcomeState() {
    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(24.0),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: Colors.blue.shade50,
                shape: BoxShape.circle,
              ),
              child: Icon(Icons.support_agent_rounded, size: 54, color: Colors.blue.shade700),
            ),
            const SizedBox(height: 16),
            const Text(
              'Halo! Selamat Datang di Bobby Computer 👋',
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.bold,
                color: Color(0xFF1E293B),
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'Saya siap membantu Kakak mencari laptop, desktop, printer, dan monitor sesuai kebutuhan dan budget.',
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 14, color: Colors.grey.shade600),
            ),
            const SizedBox(height: 24),
            const Text(
              'Coba tanyakan hal berikut:',
              style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: Color(0xFF475569)),
            ),
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              alignment: WrapAlignment.center,
              children: _quickSuggestions.map((query) {
                return ActionChip(
                  avatar: const Icon(Icons.chat_bubble_outline, size: 16, color: Colors.blue),
                  label: Text(query, style: const TextStyle(fontSize: 13)),
                  backgroundColor: Colors.white,
                  side: BorderSide(color: Colors.blue.shade100),
                  onPressed: () => _handleSend(query),
                );
              }).toList(),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildMessageItem(ChatMessage msg) {
    if (msg.isUser) {
      return Padding(
        padding: const EdgeInsets.only(bottom: 16.0),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.end,
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            const Spacer(flex: 1),
            Flexible(
              flex: 4,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                decoration: BoxDecoration(
                  color: Colors.blue.shade700,
                  borderRadius: const BorderRadius.only(
                    topLeft: Radius.circular(16),
                    topRight: Radius.circular(16),
                    bottomLeft: Radius.circular(16),
                    bottomRight: Radius.circular(4),
                  ),
                ),
                child: Text(
                  msg.text,
                  style: const TextStyle(color: Colors.white, fontSize: 14.5, height: 1.4),
                ),
              ),
            ),
          ],
        ),
      );
    }

    // Assistant message
    return Padding(
      padding: const EdgeInsets.only(bottom: 20.0),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          CircleAvatar(
            radius: 18,
            backgroundColor: Colors.blue.shade100,
            child: Icon(Icons.support_agent_rounded, size: 20, color: Colors.blue.shade800),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: const BorderRadius.only(
                      topLeft: Radius.circular(4),
                      topRight: Radius.circular(16),
                      bottomLeft: Radius.circular(16),
                      bottomRight: Radius.circular(16),
                    ),
                    boxShadow: [
                      BoxShadow(
                        color: Colors.black.withValues(alpha: 0.04),
                        blurRadius: 8,
                        offset: const Offset(0, 2),
                      ),
                    ],
                    border: Border.all(color: const Color(0xFFE2E8F0)),
                  ),
                  child: MarkdownBody(
                    data: msg.text,
                    styleSheet: MarkdownStyleSheet.fromTheme(Theme.of(context)).copyWith(
                      p: const TextStyle(fontSize: 14.5, height: 1.5, color: Color(0xFF1E293B)),
                      strong: const TextStyle(fontWeight: FontWeight.bold, color: Color(0xFF0F172A)),
                      listBullet: const TextStyle(color: Colors.blue),
                    ),
                  ),
                ),

                // Products cards list if any
                if (msg.products.isNotEmpty) ...[
                  const SizedBox(height: 12),
                  _buildProductCards(msg.products),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildProductCards(List<Product> products) {
    return SizedBox(
      height: 250,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        itemCount: products.length,
        separatorBuilder: (_, _) => const SizedBox(width: 12),
        itemBuilder: (context, index) {
          final prod = products[index];
          final imgUrl = ApiService.resolveImageUrl(prod.imageUrl);

          return Container(
            width: 220,
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: Colors.blue.shade100),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withValues(alpha: 0.03),
                  blurRadius: 6,
                  offset: const Offset(0, 2),
                ),
              ],
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Product Image
                ClipRRect(
                  borderRadius: const BorderRadius.vertical(top: Radius.circular(12)),
                  child: Image.network(
                    imgUrl,
                    height: 110,
                    width: double.infinity,
                    fit: BoxFit.cover,
                    errorBuilder: (context, error, stackTrace) {
                      return Container(
                        height: 110,
                        color: Colors.grey.shade100,
                        child: Center(
                          child: Icon(Icons.devices, size: 40, color: Colors.grey.shade400),
                        ),
                      );
                    },
                  ),
                ),

                // Details
                Padding(
                  padding: const EdgeInsets.all(10.0),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        prod.nama,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        prod.formattedPrice,
                        style: TextStyle(
                          color: Colors.blue.shade800,
                          fontWeight: FontWeight.w700,
                          fontSize: 13,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        '${prod.prosesor.isNotEmpty ? prod.prosesor : prod.brand} • ${prod.ram}',
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(fontSize: 11, color: Colors.grey.shade600),
                      ),
                      const SizedBox(height: 8),
                      SizedBox(
                        width: double.infinity,
                        height: 28,
                        child: OutlinedButton(
                          style: OutlinedButton.styleFrom(
                            padding: EdgeInsets.zero,
                            side: BorderSide(color: Colors.blue.shade300),
                            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(6)),
                          ),
                          onPressed: () => _handleSend('Bisa jelaskan lebih detail tentang ${prod.nama}?'),
                          child: const Text('Tanya Detail', style: TextStyle(fontSize: 11)),
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          );
        },
      ),
    );
  }

  Widget _buildTypingIndicator() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16.0, vertical: 8.0),
      child: Row(
        children: [
          CircleAvatar(
            radius: 16,
            backgroundColor: Colors.blue.shade50,
            child: Icon(Icons.support_agent_rounded, size: 18, color: Colors.blue.shade600),
          ),
          const SizedBox(width: 10),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: const Color(0xFFE2E8F0)),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                SizedBox(
                  width: 12,
                  height: 12,
                  child: CircularProgressIndicator(strokeWidth: 2, color: Colors.blue.shade700),
                ),
                const SizedBox(width: 8),
                Text(
                  'CS Bobby sedang mengetik...',
                  style: TextStyle(fontSize: 12.5, color: Colors.grey.shade600, fontStyle: FontStyle.italic),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSuggestionsBar() {
    return Container(
      height: 38,
      margin: const EdgeInsets.only(bottom: 8),
      child: ListView.separated(
        padding: const EdgeInsets.symmetric(horizontal: 16),
        scrollDirection: Axis.horizontal,
        itemCount: _quickSuggestions.length,
        separatorBuilder: (_, _) => const SizedBox(width: 8),
        itemBuilder: (context, index) {
          final s = _quickSuggestions[index];
          return ActionChip(
            label: Text(s, style: const TextStyle(fontSize: 12)),
            backgroundColor: Colors.white,
            side: BorderSide(color: Colors.grey.shade300),
            padding: const EdgeInsets.symmetric(horizontal: 4),
            onPressed: () => _handleSend(s),
          );
        },
      ),
    );
  }

  Widget _buildInputArea() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: const BoxDecoration(
        color: Colors.white,
        border: Border(top: BorderSide(color: Color(0xFFE2E8F0))),
      ),
      child: Row(
        children: [
          Expanded(
            child: TextField(
              controller: _textController,
              decoration: InputDecoration(
                hintText: 'Ketik pesan atau pertanyaan tentang komputer...',
                hintStyle: TextStyle(fontSize: 14, color: Colors.grey.shade500),
                contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(24),
                  borderSide: BorderSide(color: Colors.grey.shade300),
                ),
                focusedBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(24),
                  borderSide: BorderSide(color: Colors.blue.shade600, width: 1.5),
                ),
                filled: true,
                fillColor: const Color(0xFFF8FAFC),
              ),
              onSubmitted: (_) => _handleSend(),
            ),
          ),
          const SizedBox(width: 10),
          Material(
            color: Colors.blue.shade700,
            borderRadius: BorderRadius.circular(24),
            child: InkWell(
              borderRadius: BorderRadius.circular(24),
              onTap: _isLoading ? null : () => _handleSend(),
              child: const Padding(
                padding: EdgeInsets.all(12.0),
                child: Icon(Icons.send_rounded, color: Colors.white, size: 20),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
