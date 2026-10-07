import 'product.dart';

class ChatMessage {
  final String text;
  final bool isUser;
  final DateTime timestamp;
  final List<Product> products;
  final String? route;
  final String? state;
  final String? action;

  ChatMessage({
    required this.text,
    required this.isUser,
    required this.timestamp,
    this.products = const [],
    this.route,
    this.state,
    this.action,
  });

  factory ChatMessage.fromAssistantJson(Map<String, dynamic> json) {
    List<Product> prods = [];
    if (json['products'] != null && json['products'] is List) {
      prods = (json['products'] as List)
          .map((p) => Product.fromJson(p as Map<String, dynamic>))
          .toList();
    }

    return ChatMessage(
      text: json['reply'] ?? json['text'] ?? '',
      isUser: false,
      timestamp: json['timestamp'] != null
          ? DateTime.fromMillisecondsSinceEpoch(
              ((json['timestamp'] as num) * 1000).toInt(),
            )
          : DateTime.now(),
      products: prods,
      route: json['route'],
      state: json['state'],
      action: json['action'],
    );
  }

  factory ChatMessage.fromHistoryJson(Map<String, dynamic> json) {
    final sender = (json['sender'] ?? json['role'] ?? '').toString().toLowerCase();
    final isUser = sender == 'user';
    List<Product> prods = [];
    if (json['products'] != null && json['products'] is List) {
      prods = (json['products'] as List)
          .map((p) => Product.fromJson(p as Map<String, dynamic>))
          .toList();
    }

    return ChatMessage(
      text: json['text'] ?? '',
      isUser: isUser,
      timestamp: json['timestamp'] != null
          ? DateTime.fromMillisecondsSinceEpoch(
              ((json['timestamp'] as num) * 1000).toInt(),
            )
          : DateTime.now(),
      products: prods,
      route: json['route'],
      state: json['state'],
    );
  }
}
