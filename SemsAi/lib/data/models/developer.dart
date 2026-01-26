import 'package:equatable/equatable.dart';

class Developer extends Equatable {
  final String? id;
  final String devName;
  final int projectsCompleted;
  final int totalProjects;
  final String specialization;
  final double rating;
  final String devHistory;

  const Developer({
    this.id,
    required this.devName,
    required this.projectsCompleted,
    required this.totalProjects,
    required this.specialization,
    required this.rating,
    required this.devHistory,
  });

  Map<String, dynamic> toJson() => {
    'dev_name': devName,
    'projects_completed': projectsCompleted,
    'total_projects': totalProjects,
    'specialization': specialization,
    'rating': rating,
    'dev_history': devHistory,
  };

  factory Developer.fromJson(Map<String, dynamic> json) => Developer(
    id: json['_id'] as String?,
    devName: json['dev_name'] ?? '',
    projectsCompleted: json['projects_completed'] ?? 0,
    totalProjects: json['total_projects'] ?? 0,
    specialization: json['specialization'] ?? '',
    rating: json['rating'] ?? 0.0,
    devHistory: json['dev_history'] ?? '',
  );

  @override
  List<Object?> get props => [
    id,
    devName,
    projectsCompleted,
    totalProjects,
    specialization,
    rating,
    devHistory,
  ];
}
