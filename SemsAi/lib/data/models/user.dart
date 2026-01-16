import 'package:equatable/equatable.dart';

class User extends Equatable {
  final String? id;
  final String name;
  final String pass;
  final String email;
  final String? profession;
  final String? occupation;
  final List<String> devPreference;
  final List<String> amenities;

  const User({
    this.id,
    required this.name,
    required this.pass,
    required this.email,
    this.profession,
    this.occupation,
    this.devPreference = const [],
    this.amenities = const [],
  });

  Map<String, dynamic> toJson() => {
    'name': name,
    'pass': pass,
    'email': email.toLowerCase(),
    'profession': profession,
    'occupation': occupation,
    'dev_preference': devPreference,
    'amenities': amenities,
  };

  factory User.fromJson(Map<String, dynamic> json) => User(
    id: json['_id'] as String?,
    name: json['name'] ?? '',
    pass: json['pass'] ?? '',
    email: json['email'].toLowerCase() ?? '',
    profession: json['profession'],
    occupation: json['occupation'],
    devPreference: List<String>.from(json['dev_preference'] ?? []),
    amenities: List<String>.from(json['amenities'] ?? []),
  );

  @override
  List<Object?> get props => [
    id,
    name,
    email,
    profession,
    occupation,
    devPreference,
    amenities,
  ];
}
