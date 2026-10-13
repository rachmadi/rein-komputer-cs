import 'dart:convert';
import 'dart:math';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import '../models/chat_message.dart';
import 'api_service.dart';

class ChatService {
  static const String _sessionKey = 'bobby_customer_session_id';

  static Future<String> getOrCreateSessionId() async {
    final prefs = await SharedPreferences.getInstance();
    String? sid = prefs.getString(_sessionKey);
    if (sid == null || sid.isEmpty) {
      final rand = Random().nextInt(0xFFFFFF).toRadixString(16).padLeft(6, '0');
      sid = 'web_${DateTime.now().millisecondsSinceEpoch}_$rand';
      await prefs.setString(_sessionKey, sid);
    }
    return sid;
  }

  static Future<ChatMessage> sendMessage(String text) async {
    final sessionId = await getOrCreateSessionId();
    final url = Uri.parse('${ApiService.baseUrl}/api/chat');

    final response = await http.post(
      url,
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'session_id': sessionId,
        'message': text,
      }),
    );

    if (response.statusCode == 200) {
      final data = jsonDecode(utf8.decode(response.bodyBytes));
      return ChatMessage.fromAssistantJson(data);
    } else {
      throw Exception('Gagal mengirim pesan: ${response.statusCode}');
    }
  }

  static Future<List<ChatMessage>> getHistory() async {
    final sessionId = await getOrCreateSessionId();
    final url = Uri.parse('${ApiService.baseUrl}/api/chat/history/$sessionId');

    final response = await http.get(url);
    if (response.statusCode == 200) {
      final data = jsonDecode(utf8.decode(response.bodyBytes));
      final List rawMessages = data['messages'] ?? [];
      return rawMessages.map((m) => ChatMessage.fromHistoryJson(m)).toList();
    }
    return [];
  }

  static Future<void> resetSession() async {
    final prefs = await SharedPreferences.getInstance();
    final sessionId = prefs.getString(_sessionKey);
    if (sessionId != null) {
      final url = Uri.parse('${ApiService.baseUrl}/api/chat/reset');
      await http.post(
        url,
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'session_id': sessionId}),
      );
    }
    // Generate new session ID
    final rand = Random().nextInt(0xFFFFFF).toRadixString(16).padLeft(6, '0');
    final newSid = 'web_${DateTime.now().millisecondsSinceEpoch}_$rand';
    await prefs.setString(_sessionKey, newSid);
  }
}
